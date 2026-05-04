"""
api/memory.py - 向量记忆模块

职责：
  1. 把每轮对话存入 ChromaDB（向量化）
  2. 新对话开始前，语义搜索相关历史，注入 system prompt
  3. 任何异常都不影响主流程（全部 try/catch）

依赖：
  pip install chromadb

数据存在：./chroma_data/（项目根目录下，自动创建）
"""
import os
import time
import asyncio
from typing import Optional

from api.config import get_logger

log = get_logger("memory")

# ChromaDB 数据存放路径（项目根目录下）
CHROMA_DIR = os.environ.get("CHROMA_DIR", "./chroma_data")

# 每次搜索返回的最相关历史条数
TOP_K = 3

# 单条记忆最大字符数（防止超长对话爆 context）
MAX_MEMORY_CHARS = 500

# ============================================================
# 懒加载 ChromaDB（第一次用到才初始化，不影响启动速度）
# ============================================================
_client = None
_collection = None


def _get_collection():
    """获取 ChromaDB collection，失败返回 None"""
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_or_create_collection(
            name="chat_memory",
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"[memory] ChromaDB 初始化成功，路径：{CHROMA_DIR}")
        return _collection
    except Exception as e:
        log.warning(f"[memory] ChromaDB 初始化失败（不影响主流程）: {e}")
        return None


# ============================================================
# Embedding：用 DeepSeek/OpenAI 兼容接口
# ============================================================
async def _embed(text: str) -> Optional[list[float]]:
    """把文字转成向量，失败返回 None"""
    try:
        from api.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        # DeepSeek 暂不支持 embedding，用 text-embedding-ada-002 兼容接口
        # 如果你有 OpenAI key，把下面 model 改成 text-embedding-ada-002
        # 这里用 deepseek-chat 做 embedding 降级方案（纯文字相似度）
        # ── 降级方案：直接用字符 hash 做简单向量（不依赖 embedding API）──
        # 生产环境建议换成真正的 embedding 模型
        vector = _simple_embed(text)
        return vector
    except Exception as e:
        log.warning(f"[memory] embed 失败: {e}")
        return None


def _simple_embed(text: str) -> list[float]:
    """
    简单的字符级向量（降级方案，不需要 API）。
    生产环境建议换成 text-embedding-3-small 或 bge-small-zh。
    原理：统计每个字符在文本中出现的频率，归一化成固定维度向量。
    维度：512，足够区分公考相关的不同话题。
    """
    import hashlib
    dim = 512
    vec = [0.0] * dim
    if not text:
        return vec
    for i, ch in enumerate(text[:1000]):
        idx = (ord(ch) + i * 31) % dim
        vec[idx] += 1.0
    # L2 归一化
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


# ============================================================
# 核心接口：保存记忆
# ============================================================
async def save(
    user_id: int,
    user_message: str,
    assistant_reply: str,
    session_id: Optional[str] = None,
) -> None:
    """
    把这轮对话存入向量数据库。
    在 chat_engine.bak.py 的持久化之后调用。
    失败不抛异常。
    """
    try:
        col = _get_collection()
        if col is None:
            return

        # 拼成一段完整记忆文字
        memory_text = f"用户：{user_message[:200]}\n助手：{assistant_reply[:300]}"
        memory_text = memory_text[:MAX_MEMORY_CHARS]

        vector = await _embed(memory_text)
        if vector is None:
            return

        doc_id = f"u{user_id}_{int(time.time() * 1000)}"

        # 同步调用放到线程池（chromadb 是同步的）
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: col.add(
                ids=[doc_id],
                embeddings=[vector],
                documents=[memory_text],
                metadatas=[{
                    "user_id": str(user_id),
                    "session_id": session_id or "",
                    "ts": int(time.time()),
                }],
            )
        )
        log.debug(f"[memory] 已保存记忆 user={user_id} id={doc_id}")

    except Exception as e:
        log.warning(f"[memory] save 失败（不影响主流程）: {e}")


# ============================================================
# 核心接口：搜索相关记忆
# ============================================================
async def search(
    user_id: int,
    query: str,
    top_k: int = TOP_K,
) -> str:
    """
    根据当前用户消息，搜索该用户的历史相关对话。
    返回格式化的文字，直接注入 system prompt。
    找不到或出错返回空字符串。
    """
    try:
        col = _get_collection()
        if col is None:
            return ""

        vector = await _embed(query)
        if vector is None:
            return ""

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: col.query(
                query_embeddings=[vector],
                n_results=top_k,
                where={"user_id": str(user_id)},
                include=["documents", "distances", "metadatas"],
            )
        )

        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return ""

        # 相似度过滤：cosine distance > 0.7 说明不相关，丢掉
        relevant = [
            doc for doc, dist in zip(docs, distances)
            if dist < 0.7
        ]

        if not relevant:
            return ""

        lines = ["【历史相关对话（仅供参考，不要直接复述）】"]
        for i, doc in enumerate(relevant[:top_k], 1):
            lines.append(f"{i}. {doc}")

        result = "\n".join(lines)
        log.debug(f"[memory] 搜到 {len(relevant)} 条相关记忆 user={user_id}")
        return result

    except Exception as e:
        log.warning(f"[memory] search 失败（不影响主流程）: {e}")
        return ""


# ============================================================
# 工具函数：清除某用户的所有记忆（管理用）
# ============================================================
async def clear_user_memory(user_id: int) -> int:
    """删除某用户的全部向量记忆，返回删除条数"""
    try:
        col = _get_collection()
        if col is None:
            return 0

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: col.get(
                where={"user_id": str(user_id)},
                include=["metadatas"],
            )
        )
        ids = results.get("ids", [])
        if ids:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: col.delete(ids=ids)
            )
        log.info(f"[memory] 已清除 user={user_id} 的 {len(ids)} 条记忆")
        return len(ids)
    except Exception as e:
        log.warning(f"[memory] clear 失败: {e}")
        return 0

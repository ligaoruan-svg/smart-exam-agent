"""
api/paper_routes.py - 真题下载（存量文件 + 省份 ZIP + 子集 ZIP）

接口：
    GET  /api/paper/list                列表（按省份/年份/科目筛选 + 分页）
    GET  /api/paper/provinces           32 省份统计
    GET  /api/paper/file/{paper_id}     下载单个 PDF
    GET  /api/paper/zip/{province}      下载省份整包 ZIP（预压缩）
    GET  /api/paper/zip-subset          ★ 实时打包子集（按 省+年+科目 筛选）

文件位置：
    paper.file_path  →  PROJECT_ROOT/data/...
    paper.zip_path   →  PROJECT_ROOT/zips/...
"""
import io
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse, Response

from api.auth import current_user, optional_user
from api.config import get_logger
from api.db import query_all, query_one, execute

log = get_logger("api")

router = APIRouter(prefix="/api/paper", tags=["paper"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# 列表（DownloadPanel 主表 + ChatPanel 给 AI 用都可调）
# ============================================================
@router.get("/list")
def list_papers(
    province:  Optional[str] = Query(None),
    year:      Optional[int] = Query(None),
    exam_type: Optional[str] = Query(None, description="行测 / 申论"),
    doc_type:  Optional[str] = Query(None, description="题目 / 答案"),
    keyword:   Optional[str] = Query(None),
    page:      int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conds = ["status = 'published'"]
    params: list = []
    if province:
        conds.append("province = %s"); params.append(province)
    if year:
        conds.append("year = %s"); params.append(int(year))
    if exam_type:
        conds.append("exam_type = %s"); params.append(exam_type)
    if doc_type:
        conds.append("doc_type = %s"); params.append(doc_type)
    if keyword:
        conds.append("(name LIKE %s OR province LIKE %s)")
        like = f"%{keyword}%"
        params.extend([like, like])
    where = " AND ".join(conds)

    total = query_one(f"SELECT COUNT(*) AS n FROM papers WHERE {where}",
                       tuple(params))["n"]
    offset = (page - 1) * page_size
    rows = query_all(
        f"SELECT id, name, province, year, exam_type, doc_type, sub_exam, "
        f"       file_size, download_count "
        f"FROM papers WHERE {where} "
        f"ORDER BY year DESC, province ASC, exam_type ASC, doc_type ASC "
        f"LIMIT %s OFFSET %s",
        tuple(params) + (page_size, offset),
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id":            r["id"],
                "name":          r["name"],
                "province":      r["province"],
                "year":          r["year"],
                "exam_type":     r["exam_type"],
                "doc_type":      r["doc_type"],
                "sub_exam":      r["sub_exam"],
                "size_mb":       round((r["file_size"] or 0) / 1024 / 1024, 2),
                "size_bytes":    r["file_size"] or 0,
                "download_count": r["download_count"] or 0,
                "download_url":  f"/api/paper/file/{r['id']}",
            }
            for r in rows
        ],
    }


# ============================================================
# 省份统计 - DownloadPanel 用
# ============================================================
@router.get("/provinces")
def list_provinces():
    """
    返回:
      provinces: 每个省份的真题统计（paper 数 / 整包 ZIP）
      extras:    zips/ 目录里非省份维度的"专题资料 ZIP"，
                 例如 申论行测技巧.zip。前端混在省份卡片旁边一起展示。
    """
    # ---------- 1. 省份维度（来自 papers 表 GROUP BY） ----------
    rows = query_all(
        "SELECT province, "
        "       COUNT(*)        AS files, "
        "       SUM(file_size)  AS size_bytes, "
        "       MAX(zip_path)   AS zip_path "
        "FROM papers WHERE status = 'published' "
        "GROUP BY province ORDER BY files DESC"
    )
    out: list = []
    matched_zip_names: set = set()  # 已被某省份引用的 zip 文件名

    for r in rows:
        zip_rel  = r["zip_path"]
        zip_size = None
        if zip_rel:
            zp = PROJECT_ROOT / zip_rel
            if zp.exists():
                zip_size = zp.stat().st_size
                matched_zip_names.add(zp.name)
            else:
                zip_rel = None

        out.append({
            "province":   r["province"],
            "files":      int(r["files"] or 0),
            "size_mb":    round((r["size_bytes"] or 0) / 1024 / 1024, 1),
            "has_zip":    bool(zip_rel),
            "zip_size_mb": round((zip_size or 0) / 1024 / 1024, 1) if zip_size else None,
            "zip_url":    f"/api/paper/zip/{r['province']}" if zip_rel else None,
        })

    # ---------- 2. 专题资料（zips/ 里没被省份认领的 ZIP） ----------
    extras: list = []
    zips_dir = PROJECT_ROOT / "zips"
    if zips_dir.exists():
        for zf in sorted(zips_dir.glob("*.zip")):
            if zf.name in matched_zip_names:
                continue   # 已经在某省份卡片里了
            # 友好显示名：去掉 .zip 后缀
            label = zf.stem
            extras.append({
                "name":     label,                          # 申论行测技巧
                "filename": zf.name,                        # 申论行测技巧.zip
                "size_mb":  round(zf.stat().st_size / 1024 / 1024, 1),
                "zip_url":  f"/api/paper/zip-extra/{label}",
            })

    return {
        "count":     len(out),
        "provinces": out,
        "extras":    extras,
    }


# ============================================================
# 专题资料 ZIP 下载
# ============================================================
@router.get("/zip-extra/{name}")
def download_extra_zip(
    name: str,
    user: Optional[dict] = Depends(optional_user),
):
    """下载非省份维度的专题资料（如 zips/申论行测技巧.zip）"""
    # 安全：不允许 .. 或斜杠
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "不合法的资料名")
    full = PROJECT_ROOT / "zips" / f"{name}.zip"
    if not full.exists():
        raise HTTPException(404, f"未找到资料: {name}.zip")
    return FileResponse(
        path=full,
        filename=f"{name}.zip",
        media_type="application/zip",
    )


# ============================================================
# 单文件下载
# ============================================================
@router.get("/file/{paper_id}")
def download_paper(paper_id: int, user: Optional[dict] = Depends(optional_user)):
    """
    下载单份真题 PDF。
    鉴权：可选——未登录也允许下载（公开资源），登录的话顺便累计 download_count。
    """
    p = query_one(
        "SELECT id, name, file_path, file_size FROM papers "
        "WHERE id = %s AND status = 'published'",
        (paper_id,),
    )
    if not p:
        raise HTTPException(404, "试卷不存在或未发布")

    rel = p["file_path"]
    if not rel:
        raise HTTPException(404, "试卷未关联文件")

    full = PROJECT_ROOT / rel
    if not full.exists():
        log.warning(f"⚠️  paper {paper_id} 文件丢失: {full}")
        raise HTTPException(404, "文件已丢失或被移动")

    # 累计下载次数
    try:
        execute("UPDATE papers SET download_count = COALESCE(download_count, 0) + 1 "
                "WHERE id = %s", (paper_id,))
    except Exception as e:
        log.warning(f"累计下载数失败: {e}")

    # 用 paper.name 做下载文件名（友好），后端原文件名可能很乱
    download_name = (p["name"] or full.name) + ".pdf" \
                    if not (p["name"] or "").endswith(".pdf") else (p["name"] or full.name)

    return FileResponse(
        path=full,
        filename=download_name,
        media_type="application/pdf",
    )


# ============================================================
# 省份整包 ZIP 下载
# ============================================================
@router.get("/zip/{province}")
def download_province_zip(
    province: str,
    user: Optional[dict] = Depends(optional_user),
):
    # zip_path 是相对路径
    rel = f"zips/{province}公考真题.zip"
    full = PROJECT_ROOT / rel
    if not full.exists():
        raise HTTPException(404, f"未找到 {province} 的整包 ZIP")

    return FileResponse(
        path=full,
        filename=f"{province}公考真题.zip",
        media_type="application/zip",
    )


# ============================================================
# 子集 ZIP 实时打包（多年份 / 多科目 / 多 doc_type）
# ============================================================
def _parse_csv(s: Optional[str]) -> list:
    """把 '2021,2022,2023' 或 '行测,申论' 切成列表"""
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


@router.get("/zip-subset")
def download_subset_zip(
    province:  str           = Query(..., description="省份，必填"),
    years:     Optional[str] = Query(None, description="逗号分隔，如 '2021,2022,2023'"),
    exam_type: Optional[str] = Query(None, description="逗号分隔，如 '行测' 或 '行测,申论'"),
    doc_type:  Optional[str] = Query(None, description="逗号分隔，如 '题目,答案'"),
    user: Optional[dict] = Depends(optional_user),
):
    """
    根据筛选条件实时打包真题 ZIP 流式返回。
    例：/api/paper/zip-subset?province=广东&years=2021,2022,2023&exam_type=行测
        → 广东_2021+2022+2023_行测.zip
    """
    year_list      = [int(y) for y in _parse_csv(years) if y.isdigit()]
    exam_type_list = _parse_csv(exam_type)
    doc_type_list  = _parse_csv(doc_type)

    # 组装 SQL
    conds  = ["province = %s", "status = 'published'"]
    params: list = [province]
    if year_list:
        placeholders = ",".join(["%s"] * len(year_list))
        conds.append(f"year IN ({placeholders})")
        params.extend(year_list)
    if exam_type_list:
        placeholders = ",".join(["%s"] * len(exam_type_list))
        conds.append(f"exam_type IN ({placeholders})")
        params.extend(exam_type_list)
    if doc_type_list:
        placeholders = ",".join(["%s"] * len(doc_type_list))
        conds.append(f"doc_type IN ({placeholders})")
        params.extend(doc_type_list)

    rows = query_all(
        f"SELECT id, name, file_path FROM papers "
        f"WHERE {' AND '.join(conds)} "
        f"ORDER BY year DESC, exam_type, doc_type",
        tuple(params),
    )
    if not rows:
        raise HTTPException(404, "未找到符合条件的试卷")

    # 实际能打开的文件
    valid: list = []
    for r in rows:
        rel = r.get("file_path")
        if not rel:
            continue
        full = PROJECT_ROOT / rel
        if full.exists():
            valid.append((r["name"], full))

    if not valid:
        raise HTTPException(404, "符合条件的试卷文件已丢失")

    # 起友好文件名：广东_2021+2022+2023_行测_题目.zip
    name_parts = [province]
    if year_list:
        name_parts.append("+".join(str(y) for y in sorted(set(year_list))))
    if exam_type_list:
        name_parts.append("+".join(exam_type_list))
    if doc_type_list and len(doc_type_list) < 2:   # 只有"题目"或只有"答案"才标
        name_parts.append("+".join(doc_type_list))
    base_name = "_".join(name_parts)
    zip_filename = f"{base_name}.zip"

    # 流式输出（边压边发，文件多时不占用内存）
    def iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for friendly_name, full_path in valid:
                # 防同名 → 加 paper id 后缀
                arc_name = f"{friendly_name}.pdf"
                try:
                    zf.write(full_path, arcname=arc_name)
                except Exception as e:
                    log.warning(f"打包跳过 {full_path}: {e}")
        buf.seek(0)
        yield from buf

    # 累计下载次数（对所有命中的 paper）
    try:
        ids = [r["id"] for r in rows]
        if ids:
            ph = ",".join(["%s"] * len(ids))
            execute(
                f"UPDATE papers SET download_count = COALESCE(download_count, 0) + 1 "
                f"WHERE id IN ({ph})",
                tuple(ids),
            )
    except Exception as e:
        log.warning(f"累计下载数失败: {e}")

    # 中文文件名要 RFC 5987 编码，否则浏览器拿到乱码
    encoded = quote(zip_filename)
    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{encoded}\"; "
                f"filename*=UTF-8''{encoded}"
            ),
        },
    )


@router.get("/subset-info")
def subset_info(
    province:  str           = Query(...),
    years:     Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    doc_type:  Optional[str] = Query(None),
):
    """
    给 MCP 工具用的"预查"接口：返回筛选下的文件数 + 总大小估算 + 友好文件名。
    LLM 调用 trigger_pack_province 时，MCP 工具内部直接查 DB，不走这个接口。
    保留这个接口方便前端在某些场景下也能直接调。
    """
    year_list      = [int(y) for y in _parse_csv(years) if y.isdigit()]
    exam_type_list = _parse_csv(exam_type)
    doc_type_list  = _parse_csv(doc_type)

    conds  = ["province = %s", "status = 'published'"]
    params: list = [province]
    if year_list:
        ph = ",".join(["%s"] * len(year_list))
        conds.append(f"year IN ({ph})"); params.extend(year_list)
    if exam_type_list:
        ph = ",".join(["%s"] * len(exam_type_list))
        conds.append(f"exam_type IN ({ph})"); params.extend(exam_type_list)
    if doc_type_list:
        ph = ",".join(["%s"] * len(doc_type_list))
        conds.append(f"doc_type IN ({ph})"); params.extend(doc_type_list)

    row = query_one(
        f"SELECT COUNT(*) AS n, SUM(file_size) AS total FROM papers "
        f"WHERE {' AND '.join(conds)}",
        tuple(params),
    )
    n     = (row or {}).get("n") or 0
    total = (row or {}).get("total") or 0
    return {
        "count":   int(n),
        "size_mb": round(total / 1024 / 1024, 1),
    }

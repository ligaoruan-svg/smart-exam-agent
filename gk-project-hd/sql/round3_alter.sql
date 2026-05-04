-- ============================================================
-- round3_alter.sql - 第三轮表结构改动
--
-- 干什么:
--   1. papers 表加 4 个字段：doc_type / sub_exam / file_path / zip_path
--      （如果你之前已经手动执行过同名 ALTER 也没关系，这里用 IF NOT EXISTS-style 写法）
--   2. 新建 pdf_jobs 表，存 PDF 异步生成任务
--
-- 跑法：
--   mysql -u root -pruanligao cs_v2 < sql/round3_alter.sql
--
-- 幂等：可重复跑，不会报错
-- ============================================================

USE cs_v2;

-- ------------------------------------------------------------
-- 1. papers 表扩展（用存储过程做幂等检查）
-- ------------------------------------------------------------
DROP PROCEDURE IF EXISTS _r3_add_col;

DELIMITER $$
CREATE PROCEDURE _r3_add_col(
    IN tbl  VARCHAR(64),
    IN col  VARCHAR(64),
    IN ddl  TEXT
)
BEGIN
    DECLARE n INT DEFAULT 0;
    SELECT COUNT(*) INTO n
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = tbl
      AND COLUMN_NAME  = col;
    IF n = 0 THEN
        SET @s = CONCAT('ALTER TABLE `', tbl, '` ADD COLUMN ', ddl);
        PREPARE stmt FROM @s;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$
DELIMITER ;

CALL _r3_add_col('papers', 'doc_type',
    "doc_type VARCHAR(20) DEFAULT NULL COMMENT '题目/答案/全套' AFTER exam_type");
CALL _r3_add_col('papers', 'sub_exam',
    "sub_exam VARCHAR(20) DEFAULT NULL COMMENT 'A/B/C 卷' AFTER doc_type");
CALL _r3_add_col('papers', 'file_path',
    "file_path VARCHAR(500) DEFAULT NULL COMMENT '本地相对路径' AFTER file_url");
CALL _r3_add_col('papers', 'zip_path',
    "zip_path VARCHAR(500) DEFAULT NULL COMMENT '所属省份 ZIP 包相对路径' AFTER file_path");

DROP PROCEDURE _r3_add_col;

-- 添加索引（如已存在不会报错的写法太啰嗦，这里直接 try/skip）
-- 改用：先看有没有，有就跳过
DROP PROCEDURE IF EXISTS _r3_add_idx;
DELIMITER $$
CREATE PROCEDURE _r3_add_idx(IN tbl VARCHAR(64), IN idx VARCHAR(64), IN col VARCHAR(64))
BEGIN
    DECLARE n INT DEFAULT 0;
    SELECT COUNT(*) INTO n
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = tbl
      AND INDEX_NAME   = idx;
    IF n = 0 THEN
        SET @s = CONCAT('ALTER TABLE `', tbl, '` ADD INDEX `', idx, '` (`', col, '`)');
        PREPARE stmt FROM @s;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$
DELIMITER ;

CALL _r3_add_idx('papers', 'idx_doc_type', 'doc_type');

DROP PROCEDURE _r3_add_idx;

-- ------------------------------------------------------------
-- 2. pdf_jobs 表：PDF 异步生成任务
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `pdf_jobs` (
    `id`             VARCHAR(36)  NOT NULL COMMENT '任务 ID（UUID），即 task_id',
    `user_id`        BIGINT UNSIGNED NOT NULL,
    `status`         VARCHAR(20)  NOT NULL DEFAULT 'pending'
                       COMMENT 'pending / running / completed / failed',
    `params`         JSON         NOT NULL COMMENT '生成参数（题数/题型/省份/题目ID列表等）',
    `question_count` INT          DEFAULT 0,
    `question_type`  VARCHAR(50)  DEFAULT NULL,
    `province`       VARCHAR(20)  DEFAULT NULL,
    `title`          VARCHAR(200) DEFAULT NULL,
    `file_name`      VARCHAR(300) DEFAULT NULL COMMENT '友好文件名',
    `file_path`      VARCHAR(500) DEFAULT NULL COMMENT '生成的 PDF 相对路径',
    `file_size`      BIGINT       DEFAULT NULL,
    `error_msg`      TEXT         DEFAULT NULL,
    `started_at`     DATETIME     DEFAULT NULL,
    `completed_at`   DATETIME     DEFAULT NULL,
    `created_at`     DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user`    (`user_id`),
    KEY `idx_status`  (`status`),
    KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PDF 异步生成任务';

-- ------------------------------------------------------------
-- 检查
-- ------------------------------------------------------------
SELECT 'round3_alter.sql 执行完成' AS msg;

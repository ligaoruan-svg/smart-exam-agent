-- ============================================================
-- 公考小智 v2 - 完整建表脚本
-- 一次性建好全部 18 张表，可独立跑通 MCP server
--
-- 使用方法（推荐建一个新库 cs_v2，跟现有 cs 共存）：
--   CREATE DATABASE cs_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
--   mysql -u root -p cs_v2 < cs_full.sql
--   mysql -u root -p cs_v2 < seed.sql
--
-- 然后从老库灌题目数据（保留你已经清洗好的 38K 道）：
--   INSERT INTO cs_v2.questions
--     SELECT NULL, province, year, exam_type, question_type, sub_type,
--            source, stem, option_a, option_b, option_c, option_d,
--            answer, analysis, content_hash, difficulty, is_valid,
--            ai_generated, total_attempts, correct_count,
--            created_at, updated_at, question_no, is_complete, remark,
--            ai_generated_answer
--     FROM cs.questions;
--   INSERT INTO cs_v2.shenglun_questions SELECT * FROM cs.shenglun_questions;
--   INSERT INTO cs_v2.users SELECT id, username, NULL, email, NULL,
--          password_hash, avatar, plan, plan_expires_at, daily_limit,
--          daily_used, daily_reset_at, total_answered, total_correct,
--          created_at, last_login_at, 'user' FROM cs.users;
--
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;


-- ============================================================
-- 一、用户与认证
-- ============================================================

-- 1. 用户表
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL COMMENT '用户名',
  `nickname` VARCHAR(50) DEFAULT NULL COMMENT '昵称（可选，没有就用 username）',
  `email` VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
  `phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  `password_hash` VARCHAR(255) DEFAULT NULL COMMENT '密码 hash',
  `avatar` VARCHAR(500) DEFAULT NULL COMMENT '头像 URL',
  `plan` VARCHAR(20) DEFAULT 'free' COMMENT 'free/pro/enterprise',
  `plan_expires_at` DATETIME DEFAULT NULL COMMENT '会员到期',
  `daily_limit` SMALLINT DEFAULT 20 COMMENT '每日免费出题数',
  `daily_used` SMALLINT DEFAULT 0 COMMENT '今日已用',
  `daily_reset_at` DATETIME DEFAULT NULL COMMENT '限额重置时间',
  `total_answered` INT UNSIGNED DEFAULT 0 COMMENT '总答题数',
  `total_correct` INT UNSIGNED DEFAULT 0 COMMENT '总答对数',
  `role` VARCHAR(20) DEFAULT 'user' COMMENT 'user / admin（管理后台鉴权）',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `last_login_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_username` (`username`),
  KEY `idx_email` (`email`),
  KEY `idx_role` (`role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';


-- ============================================================
-- 二、题库（行测 + 申论）
-- ============================================================

-- 2. 行测题库
DROP TABLE IF EXISTS `questions`;
CREATE TABLE `questions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `province` VARCHAR(20) NOT NULL COMMENT '省份：广东、国考',
  `year` SMALLINT UNSIGNED DEFAULT NULL COMMENT '年份',
  `exam_type` VARCHAR(10) DEFAULT NULL COMMENT '行测、申论',
  `question_type` VARCHAR(20) DEFAULT NULL COMMENT '言语理解/判断推理/数量关系/常识判断/图形推理/资料分析',
  `sub_type` VARCHAR(20) DEFAULT NULL COMMENT '子题型：选词填空、逻辑判断等',
  `source` VARCHAR(200) DEFAULT NULL COMMENT '原文件名',
  `stem` TEXT NOT NULL COMMENT '题干',
  `option_a` VARCHAR(500) NOT NULL COMMENT '选项 A',
  `option_b` VARCHAR(500) NOT NULL COMMENT '选项 B',
  `option_c` VARCHAR(500) NOT NULL COMMENT '选项 C',
  `option_d` VARCHAR(500) NOT NULL COMMENT '选项 D',
  `answer` CHAR(1) NOT NULL COMMENT '正确答案 A/B/C/D',
  `analysis` TEXT COMMENT '解析',
  `content_hash` CHAR(32) DEFAULT NULL COMMENT 'MD5 去重',
  `difficulty` TINYINT DEFAULT 2 COMMENT '1 简单 2 中等 3 困难',
  `is_valid` TINYINT(1) DEFAULT 1 COMMENT '1 有效 0 无效',
  `ai_generated` TINYINT(1) DEFAULT 1 COMMENT '1 AI 生成 0 人工录入',
  `total_attempts` INT UNSIGNED DEFAULT 0 COMMENT '总作答次数',
  `correct_count` INT UNSIGNED DEFAULT 0 COMMENT '答对次数',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `question_no` SMALLINT UNSIGNED DEFAULT NULL COMMENT '原卷题号',
  `is_complete` TINYINT(1) DEFAULT 1 COMMENT '1 完整 0 不完整',
  `remark` VARCHAR(200) DEFAULT NULL COMMENT '备注',
  `ai_generated_answer` TINYINT(1) DEFAULT 0 COMMENT '0 原卷答案 1 AI 推断',
  PRIMARY KEY (`id`),
  UNIQUE KEY `content_hash` (`content_hash`),
  KEY `idx_province` (`province`),
  KEY `idx_question_type` (`question_type`),
  KEY `idx_year` (`year`),
  KEY `idx_exam_type` (`exam_type`),
  KEY `idx_is_valid` (`is_valid`),
  KEY `idx_composite` (`province`, `question_type`, `is_valid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='行测题库';


-- 3. 申论题库
DROP TABLE IF EXISTS `shenglun_questions`;
CREATE TABLE `shenglun_questions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `province` VARCHAR(20) NOT NULL COMMENT '省份',
  `year` SMALLINT UNSIGNED DEFAULT NULL COMMENT '年份',
  `exam_level` VARCHAR(20) DEFAULT NULL COMMENT '副省级/地市级/行政执法/A 卷/B 卷',
  `source` VARCHAR(200) DEFAULT NULL COMMENT '原文件名',
  `question_no` TINYINT UNSIGNED DEFAULT NULL COMMENT '题号',
  `question_type` VARCHAR(20) DEFAULT NULL COMMENT '概括归纳/综合分析/对策建议/贯彻执行/申论文章',
  `stem` TEXT NOT NULL COMMENT '题目要求',
  `material` LONGTEXT COMMENT '给定材料原文',
  `word_limit` SMALLINT UNSIGNED DEFAULT NULL COMMENT '字数要求',
  `score` TINYINT UNSIGNED DEFAULT NULL COMMENT '满分',
  `key_points` JSON DEFAULT NULL COMMENT '评分要点',
  `reference_answer` TEXT COMMENT '参考答案',
  `content_hash` CHAR(32) DEFAULT NULL COMMENT 'MD5 去重',
  `is_valid` TINYINT(1) DEFAULT 1,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `content_hash` (`content_hash`),
  KEY `idx_province` (`province`),
  KEY `idx_year` (`year`),
  KEY `idx_question_type` (`question_type`),
  KEY `idx_exam_level` (`exam_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='申论题库';


-- ============================================================
-- 三、练习与答题
-- ============================================================

-- 4. 练习批次（含 AI 准备的 pending session）
DROP TABLE IF EXISTS `quiz_sessions`;
CREATE TABLE `quiz_sessions` (
  `id` CHAR(36) NOT NULL COMMENT 'UUID',
  `user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '未登录可空',
  `session_type` VARCHAR(20) DEFAULT 'random' COMMENT 'random/wrong/adaptive/ai_prepared',
  `province` VARCHAR(20) DEFAULT NULL,
  `question_type` VARCHAR(20) DEFAULT NULL,
  `paper_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '关联试卷',
  `paper_name` VARCHAR(200) DEFAULT NULL COMMENT '试卷名称快照',
  `preset_question_ids` JSON DEFAULT NULL COMMENT 'AI 准备的题目 ID 列表（pending 用）',
  `total_count` SMALLINT UNSIGNED DEFAULT NULL,
  `answered_count` SMALLINT DEFAULT 0,
  `correct_count` SMALLINT DEFAULT 0,
  `duration_seconds` INT UNSIGNED DEFAULT NULL COMMENT '总用时',
  `status` VARCHAR(20) DEFAULT 'active' COMMENT 'pending/active/completed/cancelled',
  `share_token` CHAR(20) DEFAULT NULL COMMENT '分享 token',
  `started_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `completed_at` DATETIME DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_share_token` (`share_token`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_user_status` (`user_id`, `status`),
  CONSTRAINT `quiz_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='练习批次';


-- 5. 答题记录
DROP TABLE IF EXISTS `answer_records`;
CREATE TABLE `answer_records` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `question_id` BIGINT UNSIGNED NOT NULL,
  `session_id` CHAR(36) DEFAULT NULL COMMENT '练习批次',
  `user_answer` CHAR(1) NOT NULL,
  `is_correct` TINYINT(1) NOT NULL,
  `time_spent` SMALLINT UNSIGNED DEFAULT NULL COMMENT '答题用时秒',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_question_id` (`question_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_user_correct` (`user_id`, `is_correct`),
  KEY `idx_user_created` (`user_id`, `created_at`),
  CONSTRAINT `answer_records_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `answer_records_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='答题记录';


-- 6. 错题本
DROP TABLE IF EXISTS `wrong_questions`;
CREATE TABLE `wrong_questions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `question_id` BIGINT UNSIGNED NOT NULL,
  `wrong_count` SMALLINT DEFAULT 1 COMMENT '错了几次',
  `last_wrong_at` DATETIME DEFAULT NULL,
  `is_mastered` TINYINT(1) DEFAULT 0 COMMENT '1 已掌握',
  `is_starred` TINYINT(1) DEFAULT 0 COMMENT '1 星标',
  `note` TEXT COMMENT '用户备注',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_question` (`user_id`, `question_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_is_mastered` (`is_mastered`),
  KEY `idx_question_id` (`question_id`),
  CONSTRAINT `wrong_questions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `wrong_questions_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `questions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='错题本';


-- 7. 收藏
DROP TABLE IF EXISTS `favorites`;
CREATE TABLE `favorites` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `question_id` BIGINT UNSIGNED NOT NULL,
  `target_type` VARCHAR(20) DEFAULT 'question' COMMENT 'question/shenglun',
  `note` VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_target` (`user_id`, `target_type`, `question_id`),
  KEY `idx_user` (`user_id`),
  CONSTRAINT `favorites_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='收藏夹';


-- 8. 薄弱点缓存
DROP TABLE IF EXISTS `user_weaknesses`;
CREATE TABLE `user_weaknesses` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `rate_yanyu` DECIMAL(4,3) DEFAULT 0.000 COMMENT '言语理解错误率',
  `rate_panduan` DECIMAL(4,3) DEFAULT 0.000 COMMENT '判断推理错误率',
  `rate_shuliang` DECIMAL(4,3) DEFAULT 0.000 COMMENT '数量关系错误率',
  `rate_changshi` DECIMAL(4,3) DEFAULT 0.000 COMMENT '常识判断错误率',
  `rate_shenglun` DECIMAL(4,3) DEFAULT 0.000 COMMENT '申论错误率',
  `rate_tuli` DECIMAL(4,3) DEFAULT 0.000 COMMENT '图形推理错误率',
  `rate_ziliao` DECIMAL(4,3) DEFAULT 0.000 COMMENT '资料分析错误率',
  `weakness_provinces` JSON DEFAULT NULL COMMENT '各省错误率',
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `user_weaknesses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='薄弱点';


-- ============================================================
-- 四、AI 对话
-- ============================================================

-- 9. AI 对话会话
DROP TABLE IF EXISTS `chat_sessions`;
CREATE TABLE `chat_sessions` (
  `id` CHAR(36) NOT NULL COMMENT 'UUID',
  `user_id` BIGINT UNSIGNED NOT NULL,
  `title` VARCHAR(100) DEFAULT NULL COMMENT '会话标题',
  `pinned` TINYINT(1) DEFAULT 0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_updated` (`user_id`, `updated_at`),
  CONSTRAINT `chat_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 对话会话';


-- 10. AI 对话消息
DROP TABLE IF EXISTS `chat_messages`;
CREATE TABLE `chat_messages` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `session_id` CHAR(36) NOT NULL,
  `role` VARCHAR(10) NOT NULL COMMENT 'user/assistant',
  `content` MEDIUMTEXT NOT NULL,
  `think_steps` JSON DEFAULT NULL COMMENT '思考步骤',
  `ui_cards` JSON DEFAULT NULL COMMENT 'AI 推送的卡片列表（practice_ready 等）',
  `tokens_in` INT UNSIGNED DEFAULT 0,
  `tokens_out` INT UNSIGNED DEFAULT 0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_session_created` (`session_id`, `created_at`),
  CONSTRAINT `chat_messages_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 对话消息';


-- ============================================================
-- 五、试卷与下载
-- ============================================================

-- 11. 试卷文件
DROP TABLE IF EXISTS `papers`;
CREATE TABLE `papers` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL COMMENT '试卷名',
  `province` VARCHAR(20) NOT NULL,
  `year` SMALLINT UNSIGNED NOT NULL,
  `exam_type` VARCHAR(10) NOT NULL COMMENT '行测/申论',
  `exam_level` VARCHAR(20) DEFAULT NULL,
  `file_url` VARCHAR(500) DEFAULT NULL COMMENT 'PDF URL',
  `file_size` INT UNSIGNED DEFAULT NULL COMMENT '字节',
  `download_count` INT UNSIGNED DEFAULT 0,
  `status` VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/published/offline',
  `uploader_id` BIGINT UNSIGNED DEFAULT NULL,
  `total_questions` SMALLINT UNSIGNED DEFAULT 0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_province_year` (`province`, `year`),
  KEY `idx_status` (`status`),
  KEY `idx_exam_type` (`exam_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='试卷文件';


-- 12. 下载记录
DROP TABLE IF EXISTS `paper_downloads`;
CREATE TABLE `paper_downloads` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '匿名下载可空',
  `paper_id` BIGINT UNSIGNED NOT NULL,
  `ip` VARCHAR(45) DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_paper` (`paper_id`),
  KEY `idx_created` (`created_at`),
  CONSTRAINT `paper_downloads_ibfk_1` FOREIGN KEY (`paper_id`) REFERENCES `papers` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='下载记录';


-- ============================================================
-- 六、学习计划
-- ============================================================

-- 13. 学习计划
DROP TABLE IF EXISTS `study_plans`;
CREATE TABLE `study_plans` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `target_exam` VARCHAR(50) DEFAULT NULL COMMENT '目标考试',
  `target_date` DATE DEFAULT NULL,
  `daily_goal` SMALLINT UNSIGNED DEFAULT 30 COMMENT '每日目标题数',
  `weekly_schedule` JSON DEFAULT NULL COMMENT '周排程',
  `status` VARCHAR(20) DEFAULT 'active' COMMENT 'active/paused/finished',
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_status` (`user_id`, `status`),
  CONSTRAINT `study_plans_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='学习计划';


-- ============================================================
-- 七、订单与会员
-- ============================================================

-- 14. 订单
DROP TABLE IF EXISTS `orders`;
CREATE TABLE `orders` (
  `id` VARCHAR(40) NOT NULL COMMENT '订单号 GK20260424001',
  `user_id` BIGINT UNSIGNED NOT NULL,
  `plan_key` VARCHAR(20) NOT NULL COMMENT 'pro/pdf_export...',
  `plan_name` VARCHAR(100) NOT NULL,
  `amount` DECIMAL(10,2) NOT NULL,
  `status` VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/paid/refunded/cancelled',
  `payment_method` VARCHAR(20) DEFAULT NULL COMMENT 'wechat/alipay',
  `paid_at` DATETIME DEFAULT NULL,
  `refunded_at` DATETIME DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_status` (`user_id`, `status`),
  KEY `idx_status` (`status`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='订单';


-- ============================================================
-- 八、运营与字典
-- ============================================================

-- 15. 套餐字典
DROP TABLE IF EXISTS `plans`;
CREATE TABLE `plans` (
  `id` SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `plan_key` VARCHAR(20) NOT NULL COMMENT 'free/pro/enterprise',
  `name` VARCHAR(50) NOT NULL,
  `price` DECIMAL(10,2) NOT NULL DEFAULT 0,
  `period` VARCHAR(50) DEFAULT NULL COMMENT '298元/年',
  `description` VARCHAR(200) DEFAULT NULL,
  `features` JSON NOT NULL COMMENT '权益列表',
  `is_recommended` TINYINT(1) DEFAULT 0,
  `sort_order` SMALLINT DEFAULT 0,
  `is_active` TINYINT(1) DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_plan_key` (`plan_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会员套餐';


-- 16. 省份字典
DROP TABLE IF EXISTS `provinces`;
CREATE TABLE `provinces` (
  `code` VARCHAR(20) NOT NULL,
  `name` VARCHAR(20) NOT NULL,
  `is_hot` TINYINT(1) DEFAULT 0,
  `sort_order` SMALLINT DEFAULT 0,
  `total_papers` INT UNSIGNED DEFAULT 0 COMMENT '试卷数（缓存）',
  `total_downloads` INT UNSIGNED DEFAULT 0 COMMENT '总下载（缓存）',
  PRIMARY KEY (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='省份字典';


-- 17. 公告
DROP TABLE IF EXISTS `announcements`;
CREATE TABLE `announcements` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(200) NOT NULL,
  `content` TEXT NOT NULL,
  `level` VARCHAR(20) DEFAULT 'info' COMMENT 'info/warning/success',
  `status` VARCHAR(20) DEFAULT 'draft' COMMENT 'draft/published/archived',
  `published_at` DATETIME DEFAULT NULL,
  `expires_at` DATETIME DEFAULT NULL,
  `created_by` BIGINT UNSIGNED DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_status_published` (`status`, `published_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统公告';


-- 18. 题目反馈
DROP TABLE IF EXISTS `question_feedbacks`;
CREATE TABLE `question_feedbacks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED DEFAULT NULL,
  `question_id` BIGINT UNSIGNED NOT NULL,
  `target_type` VARCHAR(20) DEFAULT 'question' COMMENT 'question/shenglun',
  `feedback_type` VARCHAR(30) NOT NULL COMMENT 'answer_wrong/stem_incomplete/option_error/analysis_error/other',
  `description` VARCHAR(1000) NOT NULL,
  `contact` VARCHAR(100) DEFAULT NULL,
  `images` JSON DEFAULT NULL,
  `status` VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/processing/resolved/rejected',
  `priority` TINYINT DEFAULT 2 COMMENT '1 低 2 中 3 高',
  `admin_reply` TEXT,
  `handler_id` BIGINT UNSIGNED DEFAULT NULL,
  `resolved_at` DATETIME DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_question` (`question_id`),
  KEY `idx_user` (`user_id`),
  KEY `idx_status_created` (`status`, `created_at`),
  KEY `idx_feedback_type` (`feedback_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='题目反馈';


-- 19. 操作日志（后台「最近动态」）
DROP TABLE IF EXISTS `activity_logs`;
CREATE TABLE `activity_logs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `actor_id` BIGINT UNSIGNED DEFAULT NULL,
  `actor_name` VARCHAR(50) DEFAULT NULL COMMENT '快照名',
  `action_type` VARCHAR(30) NOT NULL COMMENT 'upload/answer/report/upgrade/system',
  `target_type` VARCHAR(30) DEFAULT NULL,
  `target_id` VARCHAR(50) DEFAULT NULL,
  `content` VARCHAR(500) NOT NULL,
  `metadata` JSON DEFAULT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_created` (`created_at`),
  KEY `idx_action_type` (`action_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='活动流水';


SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 完毕！下一步：
--   mysql -u root -p cs_v2 < seed.sql
-- ============================================================

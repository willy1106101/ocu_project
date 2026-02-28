SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `etf_types` (
  `id` int NOT NULL,
  `name` varchar(50) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_etf_types_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (1, '債券型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (2, '市值型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (3, '產業型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (4, '配息型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (5, '區域型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (6, '反向型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (7, '槓桿型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (8, '商品期貨型 ETF');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (9, '其他/未分類');
INSERT IGNORE INTO `etf_types` (`id`, `name`) VALUES (10, '價值/成長/主題型 ETF');

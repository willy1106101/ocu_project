/*
 Navicat Premium Dump SQL

 Source Server         : Mysql_own
 Source Server Type    : MySQL
 Source Server Version : 80043 (8.0.43)
 Source Host           : localhost:3306
 Source Schema         : ocu_project

 Target Server Type    : MySQL
 Target Server Version : 80043 (8.0.43)
 File Encoding         : 65001

 Date: 30/12/2025 10:18:37
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS `ocu_project`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE `ocu_project`;

-- ----------------------------
-- Table structure for etf_composition
-- ----------------------------
DROP TABLE IF EXISTS `etf_composition`;
CREATE TABLE `etf_composition`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `etf_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `stock_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `stock_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `weight` float NOT NULL,
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 6 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of etf_composition
-- ----------------------------
INSERT INTO `etf_composition` VALUES (1, '0050', '2330', '台積電', 52);
INSERT INTO `etf_composition` VALUES (2, '0050', '2317', '鴻海', 6.5);
INSERT INTO `etf_composition` VALUES (3, '00881', '2330', '台積電', 30.1);
INSERT INTO `etf_composition` VALUES (4, '00881', '2317', '鴻海', 12.4);
INSERT INTO `etf_composition` VALUES (5, '00881', '2454', '聯發科', 15);

-- ----------------------------
-- Table structure for etf_list
-- ----------------------------
DROP TABLE IF EXISTS `etf_list`;
CREATE TABLE `etf_list`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `etf_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `risk_level` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `volatility` float NULL DEFAULT NULL,
  `sharpe_ratio` float NULL DEFAULT NULL,
  `annual_return` float NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `etf_code`(`etf_code` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of etf_list
-- ----------------------------
INSERT INTO `etf_list` VALUES (1, '0050', '元大台灣50', '中風險', NULL, 1.2, 15.5);
INSERT INTO `etf_list` VALUES (2, '0056', '元大高股息', '低風險', NULL, 0.9, 10.2);
INSERT INTO `etf_list` VALUES (3, '00881', '國泰台灣5G+', '高風險', NULL, 1.5, 22.1);

-- ----------------------------
-- Table structure for users
-- ----------------------------
-- 先移除依賴 users 的子表，避免 #1451
DROP TABLE IF EXISTS `user_portfolio`;
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `id_card` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `risk_level` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT '中風險',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `id_card`(`id_card` ASC) USING BTREE,
  UNIQUE INDEX `email`(`email` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO `users` VALUES (1, 'A123456789', 'test', 'None', 'test@test.com', 'scrypt:32768:8:1$IJL7E7FmT77pjcOJ$7e8e2c3b88e43ef689219df0b18fd259d9cf239814c6f434ff366ed9a28e8ac629b3b13d44520dc66b61f097fa9493ff9f3063577345836b2801fb5b24f7c7aa', '低風險');

-- ----------------------------
-- Table structure for user_portfolio
-- ----------------------------
CREATE TABLE `user_portfolio`  (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `stock_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `stock_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `buy_price` float NULL DEFAULT NULL,
  `dividend` float NULL DEFAULT NULL,
  `current_price` float NULL DEFAULT NULL,
  `buy_date` date NULL DEFAULT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `user_id`(`user_id` ASC) USING BTREE,
  CONSTRAINT `user_portfolio_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of user_portfolio
-- ----------------------------

SET FOREIGN_KEY_CHECKS = 1;

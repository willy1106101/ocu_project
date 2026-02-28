#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import pymysql

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ocu_app.core.config import AppConfig  # noqa: E402


SQL_FILES = (
    ROOT_DIR / "database" / "schema" / "schema.sql",
    ROOT_DIR / "database" / "seed" / "etf_types.sql",
    ROOT_DIR / "database" / "seed" / "etf_tickers.sql",
)


def _read_sql_statements(path: Path) -> list[str]:
    sql_text = path.read_text(encoding="utf-8")
    lines: list[str] = []
    in_block_comment = False

    for line in sql_text.splitlines():
        stripped = line.strip()

        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue

        if not stripped:
            continue

        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue

        if stripped.startswith("--"):
            continue

        lines.append(line)

    merged = "\n".join(lines)
    return [stmt.strip() for stmt in merged.split(";") if stmt.strip()]


def _ensure_database_exists() -> None:
    connection = pymysql.connect(
        host=AppConfig.DB_HOST,
        port=AppConfig.DB_PORT,
        user=AppConfig.DB_USER,
        password=AppConfig.DB_PASSWORD,
        charset=AppConfig.DB_CHARSET,
        connect_timeout=AppConfig.DB_CONNECT_TIMEOUT,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{AppConfig.DB_NAME}` "
                f"CHARACTER SET {AppConfig.DB_CHARSET} COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def _execute_sql_files() -> None:
    connection = pymysql.connect(
        host=AppConfig.DB_HOST,
        port=AppConfig.DB_PORT,
        user=AppConfig.DB_USER,
        password=AppConfig.DB_PASSWORD,
        database=AppConfig.DB_NAME,
        charset=AppConfig.DB_CHARSET,
        connect_timeout=AppConfig.DB_CONNECT_TIMEOUT,
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for file_path in SQL_FILES:
                if not file_path.exists():
                    raise FileNotFoundError(f"找不到 SQL 檔案: {file_path}")

                statements = _read_sql_statements(file_path)
                print(f"[init_db] 匯入 {file_path.name}（{len(statements)} statements）")

                for index, statement in enumerate(statements, start=1):
                    try:
                        cursor.execute(statement)
                    except pymysql.MySQLError as exc:
                        preview = statement.replace("\n", " ")[:140]
                        raise RuntimeError(
                            f"{file_path.name} 第 {index} 條 SQL 執行失敗: {preview}"
                        ) from exc

            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    try:
        _ensure_database_exists()
        _execute_sql_files()
        print("[init_db] 完成：資料庫與必要資料已準備好。")
        return 0
    except pymysql.MySQLError as exc:
        print("[init_db] 連線失敗，請確認 XAMPP 的 MySQL 已啟動，並檢查 .env 參數。")
        print(f"[init_db] 詳細錯誤：{exc}")
        return 1
    except Exception as exc:
        print(f"[init_db] 初始化失敗：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

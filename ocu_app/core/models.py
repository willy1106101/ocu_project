from __future__ import annotations

import pymysql

from .config import AppConfig


class DatabaseConnectionError(RuntimeError):
    """Raised when MySQL connection cannot be established."""


def get_db_connection(database: str | None = None):
    """Create a MySQL connection from environment-driven settings."""
    try:
        return pymysql.connect(
            host=AppConfig.DB_HOST,
            port=AppConfig.DB_PORT,
            user=AppConfig.DB_USER,
            password=AppConfig.DB_PASSWORD,
            database=database or AppConfig.DB_NAME,
            charset=AppConfig.DB_CHARSET,
            connect_timeout=AppConfig.DB_CONNECT_TIMEOUT,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    except pymysql.MySQLError as exc:
        raise DatabaseConnectionError(
            "無法連接資料庫，請確認 XAMPP MySQL 與 .env 設定。"
        ) from exc

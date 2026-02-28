from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _load_risk_map() -> Dict[str, Tuple[int, ...]]:
    default_map: Dict[str, Tuple[int, ...]] = {
        "低風險": (1, 4),
        "中風險": (2, 4, 10),
        "高風險": (3, 7, 8),
    }

    raw = os.getenv("RISK_TYPE_MAP_JSON")
    if not raw:
        return default_map

    try:
        parsed = json.loads(raw)
        mapped: Dict[str, Tuple[int, ...]] = {}
        for key, values in parsed.items():
            if not isinstance(values, list):
                continue
            converted = tuple(int(value) for value in values)
            if converted:
                mapped[str(key)] = converted
        return mapped or default_map
    except (ValueError, TypeError, json.JSONDecodeError):
        return default_map


class AppConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-key")
    DEBUG = _as_bool(os.getenv("FLASK_DEBUG"), True)
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = _as_int(os.getenv("FLASK_PORT"), 5000)

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = _as_int(os.getenv("DB_PORT"), 3306)
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ocu_project")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
    DB_CONNECT_TIMEOUT = _as_int(os.getenv("DB_CONNECT_TIMEOUT"), 10)

    FOCUS_ETF_LIMIT = _as_int(os.getenv("FOCUS_ETF_LIMIT"), 5)
    RECOMMEND_ETF_LIMIT = _as_int(os.getenv("RECOMMEND_ETF_LIMIT"), 6)

    ONE_YEAR_PERIOD = os.getenv("ONE_YEAR_PERIOD", "1y")
    RECENT_PERIOD = os.getenv("RECENT_PERIOD", "5d")
    COMPARE_PERIOD = os.getenv("COMPARE_PERIOD", "3mo")

    RISK_TYPE_MAP = _load_risk_map()

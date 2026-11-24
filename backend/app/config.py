"""Loads configuration from environment variables."""
import json
import os
from datetime import timedelta
from pathlib import Path

CASES_ROOT = Path(__file__).resolve().parents[2] / "cases"


def load_case() -> dict:
    """Reads cases/<case>/case.json: roles, test accounts and external API."""
    case_key = os.environ.get("CASE", "healthsync").lower()
    with open(CASES_ROOT / case_key / "case.json", encoding="utf-8") as file:
        data = json.load(file)
    data["key"] = case_key
    return data


def db_params() -> dict:
    return {
        "host": os.environ.get("DB_HOST", "db"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("MYSQL_ROOT_PASSWORD", "root"),
        "database": os.environ.get("MYSQL_DATABASE", "app"),
        "connection_timeout": 5,
    }


def load_config() -> dict:
    case = load_case()
    external_url = os.environ.get("EXTERNAL_API_BASE_URL", "").strip() or case["external_api"]["simulator_url"]
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "template-secret"),
        "SESSION_COOKIE_NAME": "session",
        # The frontend checks the cookie to know whether a session is open.
        "SESSION_COOKIE_HTTPONLY": False,
        "PERMANENT_SESSION_LIFETIME": timedelta(days=30),
        "CASE": case,
        "DB": db_params(),
        "WORKER_TOKEN": os.environ.get("WORKER_TOKEN", "worker-token"),
        "SMTP_HOST": os.environ.get("SMTP_HOST", "mailpit"),
        "SMTP_PORT": int(os.environ.get("SMTP_PORT", "1025")),
        "MAIL_FROM": os.environ.get("MAIL_FROM", f"no-reply@{case['key']}.test"),
        "EXTERNAL_API_BASE_URL": external_url.rstrip("/"),
        "EXTERNAL_API_KEY": os.environ.get("EXTERNAL_API_KEY", ""),
    }

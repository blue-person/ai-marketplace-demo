# Import libraries
import json
import os
from datetime import timedelta
from pathlib import Path

# Constants
CASES_ROOT = Path(__file__).resolve().parents[2] / "cases"


# Read the case.json of the case named in CASE
def load_case() -> dict:
	case_key = os.environ.get("CASE", "healthsync").lower()
	with open(CASES_ROOT / case_key / "case.json", encoding="utf-8") as file:
		data = json.load(file)
	data["key"] = case_key
	return data


# Build the MySQL connection parameters from the environment
def db_params() -> dict:
	return {
		"host": os.environ.get("DB_HOST", "db"),
		"port": int(os.environ.get("DB_PORT", "3306")),
		"user": os.environ["DB_USER"],
		"password": os.environ["DB_PASSWORD"],
		"database": os.environ.get("MYSQL_DATABASE", "app"),
		"connection_timeout": 5,
	}


# Build the Flask configuration values from the environment and the case
def load_config() -> dict:
	case = load_case()

	# Use the environment URL when set and the case default otherwise
	external_url = os.environ.get("EXTERNAL_API_BASE_URL", "").strip() or case["external_api"]["simulator_url"]

	# The frontend reads the session cookie to detect an open session
	return {
		"SECRET_KEY": os.environ.get("SECRET_KEY", "template-secret"),
		"SESSION_COOKIE_NAME": "session",
		"SESSION_COOKIE_HTTPONLY": False,
		"PERMANENT_SESSION_LIFETIME": timedelta(days=30),
		"CASE": case,
		"DB": db_params(),
		"SMTP_HOST": os.environ.get("SMTP_HOST", "mailpit"),
		"SMTP_PORT": int(os.environ.get("SMTP_PORT", "1025")),
		"MAIL_FROM": os.environ.get("MAIL_FROM", f"no-reply@{case['key']}.test"),
		"EXTERNAL_API_BASE_URL": external_url.rstrip("/"),
		"EXTERNAL_API_KEY": os.environ.get("EXTERNAL_API_KEY", ""),
	}

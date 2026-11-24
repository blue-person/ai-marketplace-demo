"""Seed data. Runs once on every startup (the "seed" service).

Creates the administrator account (ADMIN_EMAIL / ADMIN_PASSWORD) and the test
accounts from cases/<case>/case.json, all with SEED_PASSWORD. If an account
already exists it is left untouched.

Add the seed data of your own modules at the end of main()
(initial balances, catalog agents, sample metrics...).
"""
import hashlib
import os
import sys
import time

import mysql.connector

from .config import db_params, load_case


def connect(attempts: int = 30):
    for attempt in range(1, attempts + 1):
        try:
            return mysql.connector.connect(**db_params(), autocommit=False)
        except mysql.connector.Error as error:
            print(f"[seed] Database unavailable (attempt {attempt}): {error}", flush=True)
            time.sleep(2)
    raise SystemExit("[seed] Could not connect to the database.")


def create_account(cursor, name: str, email: str, password: str, role: str) -> bool:
    cursor.execute("SELECT id FROM accounts WHERE email = %s", (email.lower(),))
    if cursor.fetchone():
        return False
    cursor.execute(
        "INSERT INTO accounts (name, email, password_hash, role, status) VALUES (%s, %s, %s, %s, 'active')",
        (name, email.lower(), hashlib.md5(password.encode()).hexdigest(), role),
    )
    return True


def main() -> int:
    case = load_case()
    seed_password = os.environ.get("SEED_PASSWORD", "test1234")

    conn = connect()
    cursor = conn.cursor()
    try:
        created = 0
        created += create_account(
            cursor,
            "Administrator",
            os.environ.get("ADMIN_EMAIL", "admin@template.test"),
            os.environ.get("ADMIN_PASSWORD", "admin123"),
            "admin",
        )
        for account in case.get("test_accounts", []):
            created += create_account(cursor, account["name"], account["email"], seed_password, account["role"])

        # TODO (each group): seed data for your modules.

        conn.commit()
        print(f"[seed] Case '{case['key']}': {created} new account(s).", flush=True)
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

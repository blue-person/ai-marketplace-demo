# Import libraries
import os
import secrets
import sys
import time
import mysql.connector

# Import modules
from .api_keys import new_api_key
from .config import db_params, load_case
from .passwords import hash_password

# Constants
SEED_CREDIT = "100.00"


# Retry the connection until the database accepts it
def connect(attempts: int = 30):
	for attempt in range(1, attempts + 1):
		try:
			return mysql.connector.connect(**db_params(), autocommit=False)
		except mysql.connector.Error as error:
			print(f"[seed] Database unavailable (attempt {attempt}): {error}", flush=True)
			time.sleep(2)
	raise SystemExit("[seed] Could not connect to the database.")


# Give the starting credit to an account and write it in the ledger
def add_seed_credit(cursor, account_id: int) -> None:
	cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (SEED_CREDIT, account_id))
	cursor.execute(
		"INSERT INTO ledger_entries (account_id, amount, entry_type) VALUES (%s, %s, 'seed_credit')",
		(account_id, SEED_CREDIT),
	)


# Return the id of the account with that email or None
def find_account_id(cursor, email: str) -> int | None:
	cursor.execute("SELECT id FROM accounts WHERE email = %s", (email.lower(),))
	row = cursor.fetchone()
	return row[0] if row else None


# Give the account its referral code and API key and print the key once
def add_access(cursor, account_id: int, email: str) -> None:
	cursor.execute("UPDATE accounts SET referral_code = %s WHERE id = %s", (secrets.token_urlsafe(8), account_id))
	api_key = new_api_key()
	cursor.execute(
		"INSERT INTO api_keys (account_id, key_hash, key_prefix) VALUES (%s, %s, %s)",
		(account_id, api_key.key_hash, api_key.prefix),
	)
	print(f"[seed] API key of {email}: {api_key.key}", flush=True)


# Insert an account unless its email is already registered
def create_account(cursor, account: dict, password: str, status: str) -> bool:
	email = account["email"].lower()
	if find_account_id(cursor, email):
		return False

	# A referrer that is not in the database leaves the column empty
	referrer_email = account.get("referred_by")
	referrer_id = find_account_id(cursor, referrer_email) if referrer_email else None

	# Store the account with a hashed password
	cursor.execute(
		"INSERT INTO accounts (name, email, password_hash, role, status, organization, country, referred_by) "
		"VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
		(
			account["name"],
			email,
			hash_password(password),
			account["role"],
			status,
			account.get("organization"),
			account.get("country"),
			referrer_id,
		),
	)
	account_id = cursor.lastrowid

	# Only active accounts that are not administrators receive credit and a key
	if status == "active" and account["role"] != "admin":
		add_seed_credit(cursor, account_id)
		add_access(cursor, account_id, email)
	return True


# Create the default accounts of the active case
def main() -> int:
	case = load_case()

	# Password shared by the test accounts and set with SEED_PASSWORD
	seed_password = os.environ.get("SEED_PASSWORD", "test1234")

	# Open the database connection and a cursor
	conn = connect()
	cursor = conn.cursor()
	try:
		created = 0

		# Create the administrator account from ADMIN_EMAIL and ADMIN_PASSWORD
		admin = {
			"name": "Administrator",
			"email": os.environ.get("ADMIN_EMAIL", "admin@template.test"),
			"role": "admin",
		}
		created += create_account(cursor, admin, os.environ.get("ADMIN_PASSWORD", "admin123"), "active")

		# Create the test accounts listed in cases/<case>/case.json
		for account in case.get("test_accounts", []):
			created += create_account(cursor, account, seed_password, "active")

		# Create the pending registrations so the approval flows can be tried
		for account in case.get("pending_accounts", []):
			created += create_account(cursor, account, seed_password, "pending")

		# The seed data of the modules goes here

		# Save all accounts in a single transaction
		conn.commit()
		print(f"[seed] Case '{case['key']}': {created} new account(s).", flush=True)
		return 0

	# Undo partial changes when seeding fails
	except Exception:
		conn.rollback()
		raise

	# Release the cursor and the connection
	finally:
		cursor.close()
		conn.close()


# Run the seed when the file is executed directly
if __name__ == "__main__":
	sys.exit(main())

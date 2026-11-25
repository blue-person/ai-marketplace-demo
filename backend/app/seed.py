# Import libraries
import os
import secrets
import sys
import time
import mysql.connector

# Import modules
from .api_keys import describe_api_key, new_api_key
from .config import db_params, load_case
from .executions import request_hash
from .money import split_revenue
from .passwords import hash_password
from .schedules import validate_schedule

# Constants
SEED_CREDIT = "100.00"
MIN_SERVICE_KEY_LENGTH = 32


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


# Read the key of a robot from the environment and refuse a missing or short one
def read_service_key(variable: str) -> str:
	key = os.environ.get(variable, "")
	if len(key) < MIN_SERVICE_KEY_LENGTH:
		raise SystemExit(f"[seed] {variable} must have at least {MIN_SERVICE_KEY_LENGTH} characters.")
	return key


# Store the hash of the key of a robot and replace the previous one so a changed key applies at once
def save_service_key(cursor, account_id: int, key: str) -> None:
	api_key = describe_api_key(key)
	cursor.execute(
		"INSERT INTO api_keys (account_id, key_hash, key_prefix) VALUES (%s, %s, %s) AS new "
		"ON DUPLICATE KEY UPDATE key_hash = new.key_hash, key_prefix = new.key_prefix, created_at = CURRENT_TIMESTAMP",
		(account_id, api_key.key_hash, api_key.prefix),
	)


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

	# Only active accounts that are not administrators or robots receive credit and a key
	if status == "active" and account["role"] not in ("admin", "bot", "dispatcher", "system"):
		add_seed_credit(cursor, account_id)
		add_access(cursor, account_id, email)
	return True


# Insert an agent of the case unless its developer already has one with that name
def create_agent(cursor, agent: dict, admin_id: int) -> bool:
	developer_id = find_account_id(cursor, agent["developer"])
	cursor.execute("SELECT id FROM agents WHERE developer_id = %s AND name = %s", (developer_id, agent["name"]))
	if developer_id is None or cursor.fetchone():
		return False

	# An agent that is not pending also records the administrator that reviewed it
	reviewed = agent["status"] != "pending"
	cursor.execute(
		"INSERT INTO agents (developer_id, name, description, price_usd, category, test_endpoint, model, "
		"status, rejection_reason, reviewed_by, reviewed_at) "
		"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, " + ("CURRENT_TIMESTAMP)" if reviewed else "NULL)"),
		(
			developer_id,
			agent["name"],
			agent["description"],
			agent["price_usd"],
			agent["category"],
			agent["test_endpoint"],
			agent["model"],
			agent["status"],
			agent.get("rejection_reason"),
			admin_id if reviewed else None,
		),
	)
	return True


# Move credit of an account and write its entry of the ledger for an execution
def add_execution_credit(cursor, account_id: int, amount, entry_type: str, execution_id: int) -> None:
	cursor.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, account_id))
	cursor.execute(
		"INSERT INTO ledger_entries (account_id, amount, entry_type, execution_id) VALUES (%s, %s, %s, %s)",
		(account_id, amount, entry_type, execution_id),
	)


# Insert a finished execution of the case with its ledger entries unless the account already used its key
def create_execution(cursor, execution: dict, platform_id: int) -> bool:
	account_id = find_account_id(cursor, execution["account"])
	developer_id = find_account_id(cursor, execution["developer"])
	cursor.execute(
		"SELECT id, price_usd FROM agents WHERE developer_id = %s AND name = %s", (developer_id, execution["agent"])
	)
	agent = cursor.fetchone()
	cursor.execute(
		"SELECT id FROM executions WHERE account_id = %s AND idempotency_key = %s", (account_id, execution["key"])
	)
	if account_id is None or agent is None or cursor.fetchone():
		return False

	# The developer runs the own agent for free and the shares exist only when something was paid
	cost = 0 if account_id == developer_id else agent[1]
	completed = execution["status"] == "completed"
	developer_share, platform_fee = split_revenue(cost) if completed and cost else (None, None)
	cursor.execute(
		"INSERT INTO executions (account_id, agent_id, developer_id, idempotency_key, request_hash, prompt, response, "
		"cost_usd, developer_share, platform_fee, status, failure_reason, finished_at) "
		"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
		(
			account_id,
			agent[0],
			developer_id,
			execution["key"],
			request_hash(agent[0], execution["prompt"]),
			execution["prompt"],
			execution.get("response"),
			cost,
			developer_share,
			platform_fee,
			execution["status"],
			execution.get("failure_reason"),
		),
	)
	execution_id = cursor.lastrowid
	if cost:
		add_execution_credit(cursor, account_id, -cost, "agent_execution", execution_id)
		if completed:
			add_execution_credit(cursor, developer_id, developer_share, "agent_earning", execution_id)
			add_execution_credit(cursor, platform_id, platform_fee, "platform_fee", execution_id)
		else:
			add_execution_credit(cursor, account_id, cost, "agent_refund", execution_id)
	return True


# Insert a schedule of the case with the rules of the API unless the account already has it
def create_schedule(cursor, item: dict) -> bool:
	account_id = find_account_id(cursor, item["account"])
	developer_id = find_account_id(cursor, item["developer"])
	cursor.execute(
		"SELECT id FROM agents WHERE developer_id = %s AND name = %s AND status = 'approved'",
		(developer_id, item["agent"]),
	)
	agent = cursor.fetchone()
	if account_id is None or agent is None:
		return False
	schedule = validate_schedule({**item, "agent_id": agent[0]})
	cursor.execute(
		"SELECT id FROM scheduled_executions WHERE account_id = %s AND agent_id = %s AND prompt = %s",
		(account_id, agent[0], schedule["prompt"]),
	)
	if cursor.fetchone():
		return False

	# A paused schedule of the case was paused by its owner and the first launch comes after the delay of the case
	paused = item.get("status") == "paused"
	cursor.execute(
		"INSERT INTO scheduled_executions (account_id, agent_id, kind, prompt, interval_seconds, threshold_usd, "
		"cooldown_seconds, status, pause_reason, next_run_at) "
		"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() + INTERVAL %s SECOND)",
		(
			account_id,
			agent[0],
			schedule["kind"],
			schedule["prompt"],
			schedule["interval_seconds"],
			schedule["threshold_usd"],
			schedule["cooldown_seconds"],
			"paused" if paused else "active",
			"owner" if paused else None,
			item.get("starts_in_seconds", 0),
		),
	)
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
		admin_id = find_account_id(cursor, admin["email"])

		# Create the accounts of the system with a password nobody knows because they never sign in
		for account in case.get("system_accounts", []):
			created += create_account(cursor, account, secrets.token_urlsafe(32), "active")

		# Create the test accounts listed in cases/<case>/case.json
		for account in case.get("test_accounts", []):
			created += create_account(cursor, account, seed_password, "active")

		# Create the pending registrations so the approval flows can be tried
		for account in case.get("pending_accounts", []):
			created += create_account(cursor, account, seed_password, "pending")

		# Create the robots with a password nobody knows because they sign in with a key
		for account in case.get("service_accounts", []):
			key = read_service_key(account["api_key_env"])
			created += create_account(cursor, account, secrets.token_urlsafe(32), "active")
			save_service_key(cursor, find_account_id(cursor, account["email"]), key)

		# Create the agents of the catalog in the three statuses
		agents_created = sum(create_agent(cursor, agent, admin_id) for agent in case.get("agents", []))

		# Create the finished executions so the history, the earnings and the refunds can be seen
		cursor.execute("SELECT id FROM accounts WHERE role = 'system'")
		platform = cursor.fetchone()
		platform_id = platform[0] if platform else None
		executions_created = sum(create_execution(cursor, item, platform_id) for item in case.get("executions", []))

		# Create the schedules so the dispatch robot has something to launch
		schedules_created = sum(create_schedule(cursor, item) for item in case.get("schedules", []))

		# Save all accounts in a single transaction
		conn.commit()
		print(
			f"[seed] Case '{case['key']}': {created} new account(s) and {agents_created} new agent(s) and {executions_created} new execution(s) and {schedules_created} new schedule(s).",
			flush=True,
		)
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

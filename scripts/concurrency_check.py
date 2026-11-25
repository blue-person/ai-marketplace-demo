# Import libraries
import os
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import ROUND_DOWN, Decimal
import requests

# Constants
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080/api")
PASSWORD = os.environ["SEED_PASSWORD"]
DOMAIN = "marketplace.test"
PAUSED_SERVICES = ("dispatcher",)
RACE_TRANSFERS = 20
REFUSED_EXTRA = 10
CENT = Decimal("0.01")
MIN_FUNDS = Decimal("1.00")
TOP_UP = Decimal("20.00")
CROSSED_AMOUNT = Decimal("0.01")
INVARIANTS = {
	"accounts with a negative balance": "SELECT COUNT(*) FROM accounts WHERE balance < 0",
	"accounts whose balance differs from the sum of their ledger rows": (
		"SELECT COUNT(*) FROM accounts a WHERE a.balance <> "
		"COALESCE((SELECT SUM(amount) FROM ledger_entries l WHERE l.account_id = a.id), 0)"
	),
	"transfers without exactly two ledger rows": (
		"SELECT COUNT(*) FROM transfers t WHERE (SELECT COUNT(*) FROM ledger_entries l WHERE l.transfer_id = t.id) <> 2"
	),
	"emails registered more than once": "SELECT COUNT(*) FROM (SELECT email FROM accounts GROUP BY email HAVING COUNT(*) > 1) d",
	"completed executions whose ledger rows do not add up to zero": (
		"SELECT COUNT(*) FROM executions e WHERE e.status = 'completed' AND e.cost_usd > 0 AND "
		"(SELECT COALESCE(SUM(amount), 0) FROM ledger_entries l WHERE l.execution_id = e.id) <> 0"
	),
	"failed executions whose ledger rows do not add up to zero": (
		"SELECT COUNT(*) FROM executions e WHERE e.status = 'failed' AND "
		"(SELECT COALESCE(SUM(amount), 0) FROM ledger_entries l WHERE l.execution_id = e.id) <> 0"
	),
	"executions charged more than once": (
		"SELECT COUNT(*) FROM (SELECT execution_id FROM ledger_entries WHERE entry_type = 'agent_execution' "
		"GROUP BY execution_id HAVING COUNT(*) > 1) d"
	),
}


# Run one SQL statement in the database container and return the first value
def sql(statement: str) -> str:
	command = 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE" -N -B -e "$0"'
	result = subprocess.run(
		["docker", "compose", "exec", "-T", "db", "sh", "-c", command, statement],
		capture_output=True,
		text=True,
		check=True,
	)
	return result.stdout.strip()


# Open a session for a test account
def login(name: str) -> requests.Session:
	session = requests.Session()
	response = session.post(f"{BASE_URL}/auth/login", json={"email": f"{name}@{DOMAIN}", "password": PASSWORD})
	response.raise_for_status()
	return session


# Release all the calls at the same moment and collect the status codes
def fire(calls: list) -> dict:
	barrier = threading.Barrier(len(calls))

	# Each thread waits at the barrier before it sends its request
	def run(call):
		barrier.wait()
		return call().status_code

	with ThreadPoolExecutor(max_workers=len(calls)) as pool:
		codes = list(pool.map(run, calls))
	return {code: codes.count(code) for code in sorted(set(codes))}


# Read the balance of a test account
def balance(name: str) -> Decimal:
	return Decimal(sql(f"SELECT balance FROM accounts WHERE email = '{name}@{DOMAIN}'"))


# Send a transfer from the account of the session to a test account
def transfer(session: requests.Session, recipient: str, amount: Decimal) -> requests.Response:
	body = {"recipient_email": f"{recipient}@{DOMAIN}", "amount": f"{amount:.2f}"}
	return session.post(f"{BASE_URL}/credit/transfers", json=body)


# Print a check result and return whether it passed
def report(label: str, passed: bool, detail: str) -> bool:
	print(f"[{'PASS' if passed else 'FAIL'}] {label}: {detail}", flush=True)
	return passed


# Build a password that follows the rules of the application and changes on every run
def new_password() -> str:
	return f"{secrets.token_urlsafe(12)}Aa1!"


# Twenty simultaneous sign ups with the same email must create one account
def check_duplicate_registration() -> bool:
	email = f"race{int(time.time())}@{DOMAIN}"
	body = {"name": "Race", "email": email, "password": new_password(), "role": "developer"}
	codes = fire([lambda: requests.post(f"{BASE_URL}/auth/register", json=body)] * 20)
	rows = sql(f"SELECT COUNT(*) FROM accounts WHERE email = '{email}'")
	return report("duplicate registration", codes == {201: 1, 409: 19} and rows == "1", f"{codes}, rows {rows}")


# Transfers that add up to more than the balance must stop exactly where the balance ends
def check_no_overdraft() -> bool:
	company, developer = login("company2"), login("dev2")

	# An account without funds is topped up first so the check does not depend on earlier runs
	if balance("company2") < MIN_FUNDS:
		transfer(developer, "company2", TOP_UP).raise_for_status()
	before = balance("company2")
	amount = (before / RACE_TRANSFERS).quantize(CENT, rounding=ROUND_DOWN)
	affordable = int(before // amount)
	codes = fire([lambda: transfer(company, "dev2", amount)] * (affordable + REFUSED_EXTRA))
	after = balance("company2")
	passed = codes == {201: affordable, 402: REFUSED_EXTRA} and after == before - amount * affordable

	# The money that moved goes back so the next run starts from the same balances
	moved = before - after
	if moved > 0:
		transfer(developer, "company2", moved).raise_for_status()
	return report("no overdraft", passed, f"{codes}, balance {before} -> {after}")


# Crossed transfers between two accounts must not fail and must keep the total
def check_crossed_transfers() -> bool:
	first, second = login("dev1"), login("company1")
	total_query = f"SELECT SUM(balance) FROM accounts WHERE email IN ('dev1@{DOMAIN}', 'company1@{DOMAIN}')"
	total_before = Decimal(sql(total_query))
	calls = [lambda: transfer(first, "company1", CROSSED_AMOUNT)] * 20 + [
		lambda: transfer(second, "dev1", CROSSED_AMOUNT)
	] * 20
	codes = fire(calls)
	total_after = Decimal(sql(total_query))
	passed = codes == {201: 40} and total_before == total_after
	return report("crossed transfers", passed, f"{codes}, total {total_before} -> {total_after}")


# Every invariant of the database must hold after the tests
def check_invariants() -> bool:
	results = []
	for label, query in INVARIANTS.items():
		found = sql(query)
		results.append(report(label, found == "0", found))
	return all(results)


# Return the services of the list that are running so the checks can stop and restart them
def running_services() -> list[str]:
	result = subprocess.run(
		["docker", "compose", "ps", "--status", "running", "--services"], capture_output=True, text=True, check=True
	)
	return [name for name in PAUSED_SERVICES if name in result.stdout.split()]


# Run every check and exit with a failure code when one fails
def main() -> int:

	# The robot that launches schedules moves credit and would change the balances in the middle of a check
	paused = running_services()
	if paused:
		print(f"[INFO] Stopping {', '.join(paused)} while the checks run", flush=True)
		subprocess.run(["docker", "compose", "stop", *paused], check=True)
	try:
		results = [
			check_duplicate_registration(),
			check_no_overdraft(),
			check_crossed_transfers(),
			check_invariants(),
		]
	finally:
		if paused:
			subprocess.run(["docker", "compose", "start", *paused], check=True)
	return 0 if all(results) else 1


# Run the checks when the file is executed directly
if __name__ == "__main__":
	sys.exit(main())

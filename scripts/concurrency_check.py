# Import libraries
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import requests

# Constants
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080/api")
PASSWORD = os.environ["SEED_PASSWORD"]
DOMAIN = "marketplace.test"
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
def balance(name: str) -> str:
	return sql(f"SELECT balance FROM accounts WHERE email = '{name}@{DOMAIN}'")


# Print a check result and return whether it passed
def report(label: str, passed: bool, detail: str) -> bool:
	print(f"[{'PASS' if passed else 'FAIL'}] {label}: {detail}", flush=True)
	return passed


# Twenty simultaneous sign ups with the same email must create one account
def check_duplicate_registration() -> bool:
	email = f"race{int(time.time())}@{DOMAIN}"
	body = {"name": "Race", "email": email, "password": "a-long-password-123", "role": "developer"}
	codes = fire([lambda: requests.post(f"{BASE_URL}/auth/register", json=body)] * 20)
	rows = sql(f"SELECT COUNT(*) FROM accounts WHERE email = '{email}'")
	return report("duplicate registration", codes == {201: 1, 409: 19} and rows == "1", f"{codes}, rows {rows}")


# Thirty transfers of 5.00 from an account with 100.00 must leave exactly 20 successes
def check_no_overdraft() -> bool:
	session = login("company2")
	before = balance("company2")
	url = f"{BASE_URL}/credit/transfers"
	body = {"recipient_email": f"dev2@{DOMAIN}", "amount": "5.00"}
	codes = fire([lambda: session.post(url, json=body)] * 30)
	after = balance("company2")
	passed = codes == {201: 20, 402: 10} and after == "0.00"
	return report("no overdraft", passed, f"{codes}, balance {before} -> {after}")


# Crossed transfers between two accounts must not fail and must keep the total
def check_crossed_transfers() -> bool:
	first, second = login("dev1"), login("company1")
	total_before = sql(f"SELECT SUM(balance) FROM accounts WHERE email IN ('dev1@{DOMAIN}', 'company1@{DOMAIN}')")
	url = f"{BASE_URL}/credit/transfers"
	to_second = {"recipient_email": f"company1@{DOMAIN}", "amount": "1.00"}
	to_first = {"recipient_email": f"dev1@{DOMAIN}", "amount": "1.00"}
	codes = fire([lambda: first.post(url, json=to_second)] * 20 + [lambda: second.post(url, json=to_first)] * 20)
	total_after = sql(f"SELECT SUM(balance) FROM accounts WHERE email IN ('dev1@{DOMAIN}', 'company1@{DOMAIN}')")
	passed = codes == {201: 40} and total_before == total_after
	return report("crossed transfers", passed, f"{codes}, total {total_before} -> {total_after}")


# Every invariant of the database must hold after the tests
def check_invariants() -> bool:
	results = [report(label, sql(query) == "0", sql(query)) for label, query in INVARIANTS.items()]
	return all(results)


# Run every check and exit with a failure code when one fails
def main() -> int:
	results = [
		check_duplicate_registration(),
		check_no_overdraft(),
		check_crossed_transfers(),
		check_invariants(),
	]
	return 0 if all(results) else 1


# Run the checks when the file is executed directly
if __name__ == "__main__":
	sys.exit(main())

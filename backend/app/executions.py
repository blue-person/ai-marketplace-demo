# Import libraries
import hashlib
import json
import uuid
from decimal import Decimal
from typing import NamedTuple
from flask import abort

# Import modules
from . import audit, external_api
from .db import DuplicateError, query, retry_on_deadlock, transaction
from .money import NotEnoughBalanceError, split_revenue

# Constants
MAX_PROMPT_LENGTH = 2000
MAX_RESPONSE_LENGTH = 4000
SUMMARY_LENGTH = 200
STALE_AFTER_SECONDS = 120
HISTORY_LIMIT = 50
FAILURE_REASONS = {
	"service_unavailable": "The AI service did not answer",
	"expired": "The execution did not finish in time",
}
EXECUTION_COLUMNS = (
	"e.id, e.agent_id, a.name AS agent_name, e.status, e.cost_usd, e.prompt, e.response, "
	"e.failure_reason, e.created_at, e.finished_at"
)


# Raised when the platform account does not exist, which means the seed did not run
class PlatformAccountMissingError(RuntimeError):
	pass


# Result of the first part of an execution with the data the call to the model needs
class Charge(NamedTuple):
	execution_id: int
	model: str


# Return the idempotency key in its canonical form and refuse a missing or malformed one
def read_idempotency_key(value: str | None) -> str:
	if not value:
		abort(400, description="The Idempotency-Key header is required.")
	try:
		return str(uuid.UUID(value.strip()))
	except ValueError:
		abort(400, description="The Idempotency-Key header must be a UUID.")


# Return the prompt of the request and refuse one that is missing, empty or too long
def read_prompt(data: dict) -> str:
	value = data.get("prompt")
	if not isinstance(value, str) or not value.strip():
		abort(400, description="The prompt is required.")
	prompt = value.strip()
	if len(prompt) > MAX_PROMPT_LENGTH:
		abort(400, description=f"The prompt must have at most {MAX_PROMPT_LENGTH} characters.")
	return prompt


# Fingerprint of the request so the same key with another agent or prompt is detected
def request_hash(agent_id: int, prompt: str) -> str:
	return hashlib.sha256(json.dumps([agent_id, prompt]).encode("utf-8")).hexdigest()


# Return the id of the platform account that receives its share of every execution
def _platform_id() -> int:
	row = query("SELECT id FROM accounts WHERE role = 'system'", one=True)
	if row is None:
		raise PlatformAccountMissingError
	return row["id"]


# Lock the accounts in the order of their ids so two transactions cannot deadlock
def _lock_accounts(tx, first_id: int, second_id: int) -> None:
	tx.query("SELECT id FROM accounts WHERE id IN (%s, %s) ORDER BY id FOR UPDATE", (first_id, second_id))


# Move credit of one account and write the entry of the ledger in the same transaction
def _move_credit(tx, account_id: int, amount: Decimal, entry_type: str, execution_id: int) -> None:
	tx.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, account_id))
	tx.insert(
		"INSERT INTO ledger_entries (account_id, amount, entry_type, execution_id) VALUES (%s, %s, %s, %s)",
		(account_id, amount, entry_type, execution_id),
	)


# Save the execution as pending and charge the price in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _charge(account_id: int, agent_id: int, key: str, fingerprint: str, prompt: str) -> Charge:
	with transaction() as tx:
		agent = tx.query(
			"SELECT developer_id, price_usd, model FROM agents WHERE id = %s AND status = 'approved'",
			(agent_id,),
			one=True,
		)
		if agent is None:
			abort(404, description="The agent was not found.")

		# The developer runs the own agent for free
		cost = Decimal(0) if agent["developer_id"] == account_id else agent["price_usd"]
		execution_id = tx.insert(
			"INSERT INTO executions (account_id, agent_id, developer_id, idempotency_key, request_hash, prompt, cost_usd) "
			"VALUES (%s, %s, %s, %s, %s, %s, %s)",
			(account_id, agent_id, agent["developer_id"], key, fingerprint, prompt, cost),
		)

		# The balance is checked and changed in the same statement
		if cost > 0:
			if not tx.execute(
				"UPDATE accounts SET balance = balance - %s WHERE id = %s AND balance >= %s",
				(cost, account_id, cost),
			):
				raise NotEnoughBalanceError
			tx.insert(
				"INSERT INTO ledger_entries (account_id, amount, entry_type, execution_id) "
				"VALUES (%s, %s, 'agent_execution', %s)",
				(account_id, -cost, execution_id),
			)
		return Charge(execution_id, agent["model"])


# Close a pending execution as completed and pay the developer and the platform in one transaction
@retry_on_deadlock
def _complete(execution_id: int, response: str, platform_id: int) -> bool:
	with transaction() as tx:
		execution = tx.query(
			"SELECT account_id, agent_id, developer_id, cost_usd, status FROM executions WHERE id = %s FOR UPDATE",
			(execution_id,),
			one=True,
		)

		# An execution that was closed meanwhile is not paid a second time
		if execution["status"] != "pending":
			return False
		cost = execution["cost_usd"]
		shares = split_revenue(cost) if cost > 0 else (None, None)
		tx.execute(
			"UPDATE executions SET status = 'completed', response = %s, developer_share = %s, platform_fee = %s, "
			"finished_at = CURRENT_TIMESTAMP WHERE id = %s",
			(response[:MAX_RESPONSE_LENGTH], shares[0], shares[1], execution_id),
		)

		# The accounts are locked by id and the credit does not depend on their status
		if cost > 0:
			_lock_accounts(tx, execution["developer_id"], platform_id)
			_move_credit(tx, execution["developer_id"], shares[0], "agent_earning", execution_id)
			_move_credit(tx, platform_id, shares[1], "platform_fee", execution_id)
		audit.record(
			tx,
			"agent_executed",
			"success",
			execution["account_id"],
			execution["developer_id"],
			details={"execution_id": execution_id, "agent_id": execution["agent_id"], "cost": cost},
		)
		return True


# Close a pending execution as failed and return the price to the user in one transaction
@retry_on_deadlock
def _fail(execution_id: int, reason: str) -> bool:
	with transaction() as tx:
		execution = tx.query(
			"SELECT account_id, agent_id, developer_id, cost_usd, status FROM executions WHERE id = %s FOR UPDATE",
			(execution_id,),
			one=True,
		)

		# An execution that was closed meanwhile is not refunded a second time
		if execution["status"] != "pending":
			return False
		tx.execute(
			"UPDATE executions SET status = 'failed', failure_reason = %s, finished_at = CURRENT_TIMESTAMP "
			"WHERE id = %s",
			(reason, execution_id),
		)
		cost = execution["cost_usd"]

		# The refund is a new entry and the charge stays in the ledger
		if cost > 0:
			tx.query("SELECT id FROM accounts WHERE id = %s FOR UPDATE", (execution["account_id"],))
			_move_credit(tx, execution["account_id"], cost, "agent_refund", execution_id)
		action = "agent_execution_expired" if reason == "expired" else "agent_execution_failed"
		audit.record(
			tx,
			action,
			"failure",
			execution["account_id"],
			execution["developer_id"],
			details={"execution_id": execution_id, "agent_id": execution["agent_id"], "reason": reason, "cost": cost},
		)
		return True


# Refund the executions of the account that stayed pending for longer than any call can last
def expire_stale(account_id: int) -> None:
	stale = query(
		"SELECT id FROM executions WHERE account_id = %s AND status = 'pending' "
		"AND created_at < NOW() - INTERVAL %s SECOND",
		(account_id, STALE_AFTER_SECONDS),
	)
	for row in stale:
		_fail(row["id"], "expired")


# Return one execution of the account found by its id
def _read_execution(account_id: int, execution_id: int) -> dict | None:
	return query(
		f"SELECT {EXECUTION_COLUMNS} FROM executions e JOIN agents a ON a.id = e.agent_id "
		"WHERE e.account_id = %s AND e.id = %s",
		(account_id, execution_id),
		one=True,
	)


# Return an execution as a dictionary with the label of the failure reason
def _describe(execution: dict) -> dict:
	execution["failure_label"] = FAILURE_REASONS.get(execution["failure_reason"])
	return execution


# Answer a repeated key with the saved execution and refuse a different request or one still running
def _replay(account_id: int, key: str, fingerprint: str) -> dict:
	saved = query(
		"SELECT id, request_hash, status FROM executions WHERE account_id = %s AND idempotency_key = %s",
		(account_id, key),
		one=True,
	)
	if saved["request_hash"] != fingerprint:
		abort(422, description="The Idempotency-Key was already used with another request.")
	if saved["status"] == "pending":
		abort(409, description="A request with this Idempotency-Key is still running.")
	return _describe(_read_execution(account_id, saved["id"]))


# Run an agent for one account and return the execution and whether it was created now
def run_execution(account_id: int, agent_id: int, key: str, prompt: str) -> tuple[dict, bool]:
	expire_stale(account_id)
	fingerprint = request_hash(agent_id, prompt)

	# The platform account is read before the charge so a missing one never leaves a charge behind
	platform_id = _platform_id()
	try:
		charge = _charge(account_id, agent_id, key, fingerprint, prompt)
	except DuplicateError:
		return _replay(account_id, key, fingerprint), False

	# The model is called outside of every transaction and the result is saved in another one
	try:
		response = external_api.chat_completion(charge.model, prompt)
	except external_api.ExternalApiError:
		_fail(charge.execution_id, "service_unavailable")
	else:
		_complete(charge.execution_id, response, platform_id)
	return _describe(_read_execution(account_id, charge.execution_id)), True


# Return one execution of the account with its prompt and response or None
def get_execution(account_id: int, execution_id: int) -> dict | None:
	execution = _read_execution(account_id, execution_id)
	return _describe(execution) if execution else None


# List the latest executions of the account with a short summary of the prompt and the response
def own_executions(account_id: int) -> list[dict]:
	rows = query(
		"SELECT e.id, e.agent_id, a.name AS agent_name, e.status, e.cost_usd, e.failure_reason, e.created_at, "
		"LEFT(e.prompt, %s) AS prompt_summary, LEFT(e.response, %s) AS response_summary "
		"FROM executions e JOIN agents a ON a.id = e.agent_id WHERE e.account_id = %s ORDER BY e.id DESC LIMIT %s",
		(SUMMARY_LENGTH, SUMMARY_LENGTH, account_id, HISTORY_LIMIT),
	)
	return [_describe(row) for row in rows]


# List what the agents of a developer earned without the text of the users
def agent_earnings(developer_id: int) -> list[dict]:
	return query(
		"SELECT e.id, a.name AS agent_name, e.status, e.cost_usd, e.developer_share, e.created_at "
		"FROM executions e JOIN agents a ON a.id = e.agent_id "
		"WHERE e.developer_id = %s AND e.account_id <> e.developer_id ORDER BY e.id DESC LIMIT %s",
		(developer_id, HISTORY_LIMIT),
	)


# List the amounts of the latest executions and the totals for the administrators
def all_executions() -> dict:
	rows = query(
		"SELECT e.id, a.name AS agent_name, u.email AS user_email, e.status, e.cost_usd, "
		"e.developer_share, e.platform_fee, e.created_at "
		"FROM executions e JOIN agents a ON a.id = e.agent_id JOIN accounts u ON u.id = e.account_id "
		"ORDER BY e.id DESC LIMIT %s",
		(HISTORY_LIMIT,),
	)
	platform = query("SELECT balance FROM accounts WHERE role = 'system'", one=True)
	return {"executions": rows, "platform_balance": platform["balance"] if platform else None}

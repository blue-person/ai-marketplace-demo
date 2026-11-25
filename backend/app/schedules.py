# Import libraries
import uuid
from decimal import Decimal
from typing import NamedTuple
from flask import abort
from werkzeug.exceptions import NotFound

# Import modules
from . import audit, executions
from .db import query, retry_on_deadlock, transaction
from .money import NotEnoughBalanceError, parse_usd

# Constants
SCHEDULE_NAMESPACE = uuid.UUID("5d1b7f6e-3c42-4a8e-9b0f-7a2e6c4d8f13")
KINDS = ("recurring", "conditional")
UNIT_SECONDS = {"minutes": 60, "hours": 3600, "days": 86400}
MIN_INTERVAL_SECONDS = 300
MIN_COOLDOWN_SECONDS = 600
MAX_PERIOD_SECONDS = 30 * 86400
MAX_THRESHOLD = Decimal("9999999999.99")
MAX_OPEN_SCHEDULES = 5
MAX_FAILURES_IN_A_ROW = 3
DUE_BATCH = 20
LIST_LIMIT = 50
OWNER_PAUSES = ("owner", "failures")
ADMIN_PAUSES = ("admin",)
PAUSE_LABELS = {
	"owner": "Paused by you",
	"admin": "Paused by an administrator",
	"failures": "Paused after three failures in a row",
}
OUTCOME_LABELS = {
	"completed": "Completed",
	"failed": "The AI service did not answer and the price was returned",
	"not_enough_balance": "Skipped because the balance was not enough",
	"agent_unavailable": "Skipped because the agent is not available",
}
LIMITS = {
	"max_open_schedules": MAX_OPEN_SCHEDULES,
	"min_interval_minutes": MIN_INTERVAL_SECONDS // 60,
	"min_cooldown_minutes": MIN_COOLDOWN_SECONDS // 60,
	"max_period_days": MAX_PERIOD_SECONDS // 86400,
	"max_failures_in_a_row": MAX_FAILURES_IN_A_ROW,
}
SCHEDULE_COLUMNS = (
	"s.id, s.agent_id, a.name AS agent_name, s.kind, s.interval_seconds, s.threshold_usd, s.cooldown_seconds, "
	"s.status, s.pause_reason, s.next_run_at, s.consecutive_failures, s.last_run_at, s.last_outcome, "
	"s.last_execution_id, s.created_at"
)

# A recurring schedule moves to the next multiple of its interval that is still in the future
ADVANCE_RECURRING = (
	"UPDATE scheduled_executions SET next_run_at = next_run_at + "
	"INTERVAL ((TIMESTAMPDIFF(SECOND, next_run_at, NOW()) DIV interval_seconds) + 1) * interval_seconds SECOND "
	"WHERE id = %s"
)
ADVANCE_CONDITIONAL = (
	"UPDATE scheduled_executions SET next_run_at = NOW() + INTERVAL cooldown_seconds SECOND WHERE id = %s"
)


# Data that the launch needs after the claim and the moment of the occurrence that was claimed
class Claim(NamedTuple):
	account_id: int
	agent_id: int
	prompt: str
	occurrence: int


# True when the value is a whole number and not a boolean
def _is_whole(value) -> bool:
	return isinstance(value, int) and not isinstance(value, bool)


# Read a number and a unit from the request and return the seconds they add up to
def _read_duration(data: dict, every_key: str, unit_key: str, label: str, minimum: int) -> int:
	every, unit = data.get(every_key), data.get(unit_key)
	if not _is_whole(every) or every < 1 or unit not in UNIT_SECONDS:
		abort(400, description=f"The {label} needs a whole number and a unit of minutes, hours or days.")
	seconds = every * UNIT_SECONDS[unit]
	if not minimum <= seconds <= MAX_PERIOD_SECONDS:
		abort(
			400,
			description=f"The {label} must be between {minimum // 60} minutes and {MAX_PERIOD_SECONDS // 86400} days.",
		)
	return seconds


# Check the fields of a new schedule and return the clean values or stop with a 400
def validate_schedule(data: dict) -> dict:
	agent_id = data.get("agent_id")
	if not _is_whole(agent_id) or agent_id < 1:
		abort(400, description="The agent is required.")
	kind = data.get("kind")
	if kind not in KINDS:
		abort(400, description="The kind must be recurring or conditional.")
	schedule = {
		"agent_id": agent_id,
		"kind": kind,
		"prompt": executions.read_prompt(data),
		"interval_seconds": None,
		"threshold_usd": None,
		"cooldown_seconds": None,
	}

	# Each kind reads only its own fields and the database requires the others to be empty
	if kind == "recurring":
		schedule["interval_seconds"] = _read_duration(data, "every", "unit", "interval", MIN_INTERVAL_SECONDS)
	else:
		schedule["threshold_usd"] = parse_usd(data.get("threshold_usd"), MAX_THRESHOLD, "threshold")
		schedule["cooldown_seconds"] = _read_duration(
			data, "cooldown_every", "cooldown_unit", "cooldown", MIN_COOLDOWN_SECONDS
		)
	return schedule


# Idempotency key of one occurrence so the same occurrence is never charged twice
def occurrence_key(schedule_id: int, occurrence: int) -> str:
	return str(uuid.uuid5(SCHEDULE_NAMESPACE, f"{schedule_id}/{occurrence}"))


# Save a schedule for an account after the limit of open schedules and the agent are checked
@retry_on_deadlock
def create(account_id: int, schedule: dict) -> int:

	# The account is locked inside the transaction so two requests cannot pass the limit together
	with transaction() as tx:
		tx.query("SELECT id FROM accounts WHERE id = %s FOR UPDATE", (account_id,))
		open_schedules = tx.query(
			"SELECT COUNT(*) AS total FROM scheduled_executions WHERE account_id = %s AND status <> 'cancelled'",
			(account_id,),
			one=True,
		)["total"]
		if open_schedules >= MAX_OPEN_SCHEDULES:
			abort(409, description=f"You can have at most {MAX_OPEN_SCHEDULES} schedules that are not cancelled.")
		if (
			tx.query("SELECT id FROM agents WHERE id = %s AND status = 'approved'", (schedule["agent_id"],), one=True)
			is None
		):
			abort(404, description="The agent was not found.")

		# A recurring schedule waits one interval and a conditional one checks its balance at once
		first_delay = schedule["interval_seconds"] or 0
		schedule_id = tx.insert(
			"INSERT INTO scheduled_executions (account_id, agent_id, kind, prompt, interval_seconds, threshold_usd, "
			"cooldown_seconds, next_run_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW() + INTERVAL %s SECOND)",
			(
				account_id,
				schedule["agent_id"],
				schedule["kind"],
				schedule["prompt"],
				schedule["interval_seconds"],
				schedule["threshold_usd"],
				schedule["cooldown_seconds"],
				first_delay,
			),
		)
		audit.record(
			tx,
			"schedule_created",
			"success",
			account_id,
			account_id,
			details={"schedule_id": schedule_id, "agent_id": schedule["agent_id"], "kind": schedule["kind"]},
		)
		return schedule_id


# Change the status of a schedule with one update that checks the current status and record the event
def _change_status(schedule_id: int, actor_id: int, action: str, update_sql: str, params: tuple) -> bool:
	with transaction() as tx:
		if not tx.execute(update_sql, params):
			return False
		owner = tx.query("SELECT account_id FROM scheduled_executions WHERE id = %s", (schedule_id,), one=True)
		audit.record(tx, action, "success", actor_id, owner["account_id"], details={"schedule_id": schedule_id})
		return True


# Pause an active schedule and say who paused it and return False when it is not active
@retry_on_deadlock
def pause(schedule_id: int, actor_id: int, reason: str) -> bool:
	return _change_status(
		schedule_id,
		actor_id,
		"schedule_paused",
		"UPDATE scheduled_executions SET status = 'paused', pause_reason = %s WHERE id = %s AND status = 'active'",
		(reason, schedule_id),
	)


# Resume a paused schedule that one of the reasons allows and wait a full period before the next launch
@retry_on_deadlock
def resume(schedule_id: int, actor_id: int, reasons: tuple) -> bool:
	placeholders = ", ".join(["%s"] * len(reasons))
	return _change_status(
		schedule_id,
		actor_id,
		"schedule_resumed",
		"UPDATE scheduled_executions SET status = 'active', pause_reason = NULL, consecutive_failures = 0, "
		"next_run_at = NOW() + INTERVAL COALESCE(interval_seconds, cooldown_seconds) SECOND "
		f"WHERE id = %s AND status = 'paused' AND pause_reason IN ({placeholders})",
		(schedule_id, *reasons),
	)


# Cancel an active or paused schedule for good and return False when it was already cancelled
@retry_on_deadlock
def cancel(schedule_id: int, actor_id: int) -> bool:
	return _change_status(
		schedule_id,
		actor_id,
		"schedule_cancelled",
		"UPDATE scheduled_executions SET status = 'cancelled', pause_reason = NULL "
		"WHERE id = %s AND status IN ('active', 'paused')",
		(schedule_id,),
	)


# List the ids of the schedules that are due now and have what they need to launch
def due_ids() -> list[int]:
	rows = query(
		"SELECT s.id FROM scheduled_executions s JOIN accounts a ON a.id = s.account_id "
		"WHERE s.status = 'active' AND a.status = 'active' AND s.next_run_at <= NOW() "
		"AND (s.kind = 'recurring' OR a.balance > s.threshold_usd) ORDER BY s.next_run_at, s.id LIMIT %s",
		(DUE_BATCH,),
	)
	return [row["id"] for row in rows]


# Check that the schedule is due and move it to its next time in one transaction or return None
@retry_on_deadlock
def _claim(schedule_id: int) -> Claim | None:
	owner = query("SELECT account_id FROM scheduled_executions WHERE id = %s", (schedule_id,), one=True)
	if owner is None:
		return None

	# The account is locked before the schedule in every flow so two transactions cannot deadlock
	with transaction() as tx:
		account = tx.query(
			"SELECT status, balance FROM accounts WHERE id = %s FOR UPDATE", (owner["account_id"],), one=True
		)
		schedule = tx.query(
			"SELECT account_id, agent_id, prompt, kind, threshold_usd, UNIX_TIMESTAMP(next_run_at) AS occurrence, "
			"(status = 'active' AND next_run_at <= NOW()) AS is_due FROM scheduled_executions WHERE id = %s FOR UPDATE",
			(schedule_id,),
			one=True,
		)

		# The second request that waited for the lock finds the schedule already moved and is not due
		if not schedule["is_due"] or account["status"] != "active":
			return None
		if schedule["kind"] == "conditional" and account["balance"] <= schedule["threshold_usd"]:
			return None
		tx.execute(ADVANCE_RECURRING if schedule["kind"] == "recurring" else ADVANCE_CONDITIONAL, (schedule_id,))
		return Claim(schedule["account_id"], schedule["agent_id"], schedule["prompt"], schedule["occurrence"])


# Save the result of a launch and pause the schedule after too many failures in a row
@retry_on_deadlock
def _save_result(schedule_id: int, dispatcher_id: int, account_id: int, outcome: str, execution_id: int | None) -> None:
	with transaction() as tx:
		tx.execute(
			"UPDATE scheduled_executions SET last_run_at = NOW(), last_outcome = %s, last_execution_id = %s, "
			"consecutive_failures = IF(%s = 'completed', 0, consecutive_failures + 1) WHERE id = %s",
			(outcome, execution_id, outcome, schedule_id),
		)
		details = {"schedule_id": schedule_id, "execution_id": execution_id, "outcome": outcome}
		if outcome == "completed":
			audit.record(tx, "schedule_launched", "success", dispatcher_id, account_id, details=details)
		else:
			audit.record(tx, "schedule_launch_failed", "failure", dispatcher_id, account_id, details=details)

		# A schedule that the owner paused meanwhile is left as it is
		paused = tx.execute(
			"UPDATE scheduled_executions SET status = 'paused', pause_reason = 'failures' "
			"WHERE id = %s AND status = 'active' AND consecutive_failures >= %s",
			(schedule_id, MAX_FAILURES_IN_A_ROW),
		)
		if paused:
			audit.record(
				tx, "schedule_auto_paused", "failure", dispatcher_id, account_id, details={"schedule_id": schedule_id}
			)


# Run the agent of a schedule that is due and return what happened or None when it is not due
def launch(schedule_id: int, dispatcher_id: int) -> str | None:
	claim = _claim(schedule_id)
	if claim is None:
		return None
	key = occurrence_key(schedule_id, claim.occurrence)

	# The claim is already saved, so the model is called outside of every transaction
	execution_id = None
	try:
		execution, _created = executions.run_execution(claim.account_id, claim.agent_id, key, claim.prompt)
	except NotEnoughBalanceError:
		outcome = "not_enough_balance"
	except NotFound:
		outcome = "agent_unavailable"
	else:
		outcome, execution_id = execution["status"], execution["id"]
	_save_result(schedule_id, dispatcher_id, claim.account_id, outcome, execution_id)
	return outcome


# Add the labels of the pause reason and of the last outcome to a schedule
def _describe(schedule: dict) -> dict:
	schedule["pause_label"] = PAUSE_LABELS.get(schedule["pause_reason"])
	schedule["outcome_label"] = OUTCOME_LABELS.get(schedule["last_outcome"])
	return schedule


# List the schedules of one account with their prompt, newest first
def own_schedules(account_id: int) -> list[dict]:
	rows = query(
		f"SELECT {SCHEDULE_COLUMNS}, s.prompt FROM scheduled_executions s JOIN agents a ON a.id = s.agent_id "
		"WHERE s.account_id = %s ORDER BY s.id DESC LIMIT %s",
		(account_id, LIST_LIMIT),
	)
	return [_describe(row) for row in rows]


# List the latest schedules of everybody without the prompt for the administrators
def all_schedules() -> list[dict]:
	rows = query(
		f"SELECT {SCHEDULE_COLUMNS}, u.email AS user_email FROM scheduled_executions s "
		"JOIN agents a ON a.id = s.agent_id JOIN accounts u ON u.id = s.account_id ORDER BY s.id DESC LIMIT %s",
		(LIST_LIMIT,),
	)
	return [_describe(row) for row in rows]

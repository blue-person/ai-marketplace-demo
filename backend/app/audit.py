# Import libraries
import json
import logging

# Import modules
from .db import query, retry_on_deadlock, transaction

# Log singleton
log = logging.getLogger(__name__)

# Constants
PAGE_SIZE = 50
OUTCOMES = ("success", "failure")
ACTIONS = {
	"authn_login_success": "authn",
	"authn_login_fail": "authn",
	"authn_logout": "authn",
	"authn_api_key_fail": "authn",
	"authn_account_locked": "authn",
	"authn_account_unlocked": "authn",
	"authz_fail": "authz",
	"user_created": "registration",
	"registration_approved": "registration",
	"registration_rejected": "registration",
	"account_suspended": "account",
	"account_reactivated": "account",
	"account_renamed": "account",
	"api_key_renewed": "account",
	"audit_viewed": "account",
	"credit_transfer": "credit",
	"referral_bonus_paid": "credit",
	"agent_submitted": "agent",
	"agent_approved": "agent",
	"agent_rejected": "agent",
	"agent_executed": "execution",
	"agent_execution_failed": "execution",
	"agent_execution_expired": "execution",
	"schedule_created": "schedule",
	"schedule_paused": "schedule",
	"schedule_resumed": "schedule",
	"schedule_cancelled": "schedule",
	"schedule_launched": "schedule",
	"schedule_launch_failed": "schedule",
	"schedule_auto_paused": "schedule",
}
CATEGORIES = tuple(dict.fromkeys(ACTIONS.values()))


# Refuse an action or an outcome that the table cannot store
def _check(action: str, outcome: str) -> None:
	if action not in ACTIONS:
		raise ValueError(f"Unknown audit action {action}")
	if outcome not in OUTCOMES:
		raise ValueError(f"Unknown audit outcome {outcome}")


# Write the event inside an open transaction so it is undone together with the action
def record(
	tx,
	action: str,
	outcome: str,
	actor_id: int | None,
	target_id: int | None = None,
	target_label: str | None = None,
	details: dict | None = None,
) -> None:
	_check(action, outcome)

	# Values such as Decimal are written as text
	stored_details = json.dumps(details, default=str) if details else None
	tx.insert(
		"INSERT INTO audit_events (category, action, outcome, actor_id, target_id, target_label, details) "
		"VALUES (%s, %s, %s, %s, %s, %s, %s)",
		(ACTIONS[action], action, outcome, actor_id, target_id, target_label, stored_details),
	)

	# The table is the source of truth and this line only helps to read the container log
	log.info("audit %s %s actor=%s target=%s", action, outcome, actor_id, target_id or target_label)


# Write the event in its own transaction and repeat it after a deadlock
@retry_on_deadlock
def _record_in_new_transaction(*args, **kwargs) -> None:
	with transaction() as tx:
		record(tx, *args, **kwargs)


# Write an event that has no action to share a transaction with and never stop the request
def record_alone(
	action: str,
	outcome: str,
	actor_id: int | None,
	target_id: int | None = None,
	target_label: str | None = None,
	details: dict | None = None,
) -> None:
	_check(action, outcome)

	# A failure of the audit log must not break the answer of the application
	try:
		_record_in_new_transaction(action, outcome, actor_id, target_id, target_label, details)
	except Exception:
		log.exception("Could not store the audit event %s", action)


# Convert the JSON text of the details into a dictionary
def _read_details(value) -> dict | None:
	if isinstance(value, (str, bytes)):
		return json.loads(value)
	return value


# List the newest events first and narrow them with the filters that are given
def list_events(
	category: str | None = None,
	action: str | None = None,
	account_email: str | None = None,
	before_id: int | None = None,
) -> list[dict]:

	# Each condition has the values for its placeholders and is used only when the first one is given
	filters = {
		"e.category = %s": (category,),
		"e.action = %s": (action,),
		"(actor.email = %s OR target.email = %s OR e.target_label = %s)": (account_email,) * 3,
		"e.id < %s": (before_id,),
	}
	used = {sql: values for sql, values in filters.items() if values[0] is not None}
	conditions = list(used)
	params = [value for values in used.values() for value in values]
	where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

	# The conditions are fixed texts and every value travels as a parameter
	rows = query(
		"SELECT e.id, e.created_at, e.category, e.action, e.outcome, "
		"e.actor_id, actor.email AS actor_email, actor.role AS actor_role, "
		"e.target_id, target.email AS target_email, e.target_label, e.details "
		"FROM audit_events e "
		"LEFT JOIN accounts actor ON actor.id = e.actor_id "
		"LEFT JOIN accounts target ON target.id = e.target_id "
		f"{where} ORDER BY e.id DESC LIMIT %s",
		(*params, PAGE_SIZE),
	)
	for row in rows:
		row["details"] = _read_details(row["details"])
	return rows

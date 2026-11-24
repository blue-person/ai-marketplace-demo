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
}


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


# List the newest events first and narrow them with the filters that are not None
def list_events(
	category: str | None = None,
	action: str | None = None,
	actor_id: int | None = None,
	target_id: int | None = None,
	before_id: int | None = None,
) -> list[dict]:
	filters = {
		"e.category = %s": category,
		"e.action = %s": action,
		"e.actor_id = %s": actor_id,
		"e.target_id = %s": target_id,
		"e.id < %s": before_id,
	}
	conditions = [sql for sql, value in filters.items() if value is not None]
	params = [value for value in filters.values() if value is not None]
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

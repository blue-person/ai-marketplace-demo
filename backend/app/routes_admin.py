# Import libraries
from flask import Blueprint, abort, jsonify, request

# Import modules
from . import agents, audit, executions, schedules
from .accounts import LastAdminError, change_status, list_accounts, unlock_account
from .rbac import (
	APPROVE_REGISTRATION,
	LIST_ACCOUNTS,
	LIST_REGISTRATIONS,
	MANAGE_ACCOUNT_STATUS,
	MODERATE_SCHEDULE,
	REJECT_REGISTRATION,
	REVIEW_AGENTS,
	UNLOCK_ACCOUNT,
	VIEW_AUDIT,
	VIEW_EXECUTIONS,
	VIEW_SCHEDULES,
	require,
)
from .registration import REJECTION_REASONS, approve_account, pending_registrations, reject_account
from .security import authorized_schedule, authorized_target, current_actor, login_required, read_json_object

# Blueprint of the administrator routes
bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# Constants
NOT_PENDING = "The registration is not pending."
AGENT_NOT_PENDING = "The agent is not pending."
STATUS_NOT_CHANGEABLE = "The account is not in the status that this action needs."
LAST_ADMIN = "The platform needs at least one active administrator."
NOT_LOCKED = "The account is not locked."
SCHEDULE_NOT_ACTIVE = "The schedule is not active."
SCHEDULE_NOT_PAUSED = "The schedule is not paused by an administrator."
SCHEDULE_CANCELLED = "The schedule is already cancelled."
MAX_EMAIL_LENGTH = 254


# List the pending registrations and the reasons that can be used to reject one
@bp.get("/registrations")
@login_required
def list_registrations():
	require(current_actor(), LIST_REGISTRATIONS)
	reasons = [{"key": key, "label": label} for key, label in REJECTION_REASONS.items()]
	return jsonify(registrations=pending_registrations(), rejection_reasons=reasons)


# Approve one pending registration
@bp.post("/registrations/<int:account_id>/approve")
@login_required
def approve_registration(account_id):
	actor = current_actor()
	authorized_target(actor, APPROVE_REGISTRATION, account_id)
	if not approve_account(account_id, actor.id):
		return jsonify(error=NOT_PENDING), 409
	return jsonify(message="The account was approved.")


# Reject one pending registration with a reason from the list
@bp.post("/registrations/<int:account_id>/reject")
@login_required
def reject_registration(account_id):
	actor = current_actor()
	authorized_target(actor, REJECT_REGISTRATION, account_id)
	data = read_json_object()
	reason = str(data.get("reason", ""))
	if reason not in REJECTION_REASONS:
		abort(400, description="The reason is not valid.")
	if not reject_account(account_id, actor.id, reason):
		return jsonify(error=NOT_PENDING), 409
	return jsonify(message="The account was rejected.")


# List the pending agents and the reasons that can be used to reject one
@bp.get("/agents")
@login_required
def list_pending_agents():
	require(current_actor(), REVIEW_AGENTS)
	reasons = [{"key": key, "label": label} for key, label in agents.REJECTION_REASONS.items()]
	return jsonify(agents=agents.pending_agents(), rejection_reasons=reasons)


# Answer a review that changed nothing with a 404 when the agent does not exist and with a 409 when it is not pending
def _agent_not_reviewed(agent_id: int):
	if not agents.agent_exists(agent_id):
		abort(404, description="The agent was not found.")
	return jsonify(error=AGENT_NOT_PENDING), 409


# Approve one pending agent so it appears in the catalog
@bp.post("/agents/<int:agent_id>/approve")
@login_required
def approve_agent(agent_id):
	actor = current_actor()
	require(actor, REVIEW_AGENTS)
	if not agents.approve_agent(agent_id, actor.id):
		return _agent_not_reviewed(agent_id)
	return jsonify(message="The agent was approved.")


# Reject one pending agent with a reason from the list
@bp.post("/agents/<int:agent_id>/reject")
@login_required
def reject_agent(agent_id):
	actor = current_actor()
	require(actor, REVIEW_AGENTS)
	reason = read_json_object().get("reason")
	if not isinstance(reason, str) or reason not in agents.REJECTION_REASONS:
		abort(400, description="The reason is not valid.")
	if not agents.reject_agent(agent_id, actor.id, reason):
		return _agent_not_reviewed(agent_id)
	return jsonify(message="The agent was rejected.")


# List every account with the status action that the signed in administrator may use
@bp.get("/accounts")
@login_required
def list_all_accounts():
	actor = current_actor()
	require(actor, LIST_ACCOUNTS)
	return jsonify(accounts=list_accounts(actor))


# Check the permission and move an account from one status to the other
def _change_account_status(account_id: int, from_status: str, to_status: str, message: str):
	actor = current_actor()
	authorized_target(actor, MANAGE_ACCOUNT_STATUS, account_id)
	try:
		changed = change_status(account_id, actor.id, from_status, to_status)
	except LastAdminError:
		return jsonify(error=LAST_ADMIN), 409
	if not changed:
		return jsonify(error=STATUS_NOT_CHANGEABLE), 409
	return jsonify(message=message)


# Suspend an active account so its session and its API key stop working
@bp.post("/accounts/<int:account_id>/suspend")
@login_required
def suspend_account(account_id):
	return _change_account_status(account_id, "active", "suspended", "The account was suspended.")


# Reactivate a suspended account
@bp.post("/accounts/<int:account_id>/reactivate")
@login_required
def reactivate_account(account_id):
	return _change_account_status(account_id, "suspended", "active", "The account was reactivated.")


# Remove the lock that too many failed logins put on an account
@bp.post("/accounts/<int:account_id>/unlock")
@login_required
def unlock_locked_account(account_id):
	actor = current_actor()
	authorized_target(actor, UNLOCK_ACCOUNT, account_id)
	if not unlock_account(account_id, actor.id):
		return jsonify(error=NOT_LOCKED), 409
	return jsonify(message="The account was unlocked.")


# Read the filters of the audit log and refuse the values that are not valid
def _read_audit_filters() -> dict:
	category = request.args.get("category") or None
	action = request.args.get("action") or None
	account_email = (request.args.get("account") or "").strip().lower() or None
	before_id = request.args.get("before_id", type=int)
	if category is not None and category not in audit.CATEGORIES:
		abort(400, description="The category is not valid.")
	if action is not None and action not in audit.ACTIONS:
		abort(400, description="The action is not valid.")
	if account_email is not None and len(account_email) > MAX_EMAIL_LENGTH:
		abort(400, description="The account is not valid.")
	if "before_id" in request.args and before_id is None:
		abort(400, description="The page marker is not valid.")
	return {"category": category, "action": action, "account_email": account_email, "before_id": before_id}


# List a page of audit events and record that the administrator read them
@bp.get("/audit")
@login_required
def list_audit_events():
	actor = current_actor()
	require(actor, VIEW_AUDIT)
	filters = _read_audit_filters()
	events = audit.list_events(**filters)

	# The page marker is left out of the record because it only says which page was read
	used = {key: value for key, value in filters.items() if value is not None and key != "before_id"}
	audit.record_alone("audit_viewed", "success", actor.id, details=used or None)

	# A full page means there may be older events, and the last id is the marker to ask for them
	next_before_id = events[-1]["id"] if len(events) == audit.PAGE_SIZE else None
	return jsonify(events=events, categories=audit.CATEGORIES, next_before_id=next_before_id)


# List the amounts of the latest executions and the balance of the platform account
@bp.get("/executions")
@login_required
def list_executions():
	require(current_actor(), VIEW_EXECUTIONS)
	return jsonify(**executions.all_executions())


# List the latest schedules of everybody without their prompts
@bp.get("/schedules")
@login_required
def list_schedules():
	require(current_actor(), VIEW_SCHEDULES)
	return jsonify(schedules=schedules.all_schedules())


# Pause the schedule of any account
@bp.post("/schedules/<int:schedule_id>/pause")
@login_required
def pause_schedule(schedule_id):
	actor = current_actor()
	authorized_schedule(actor, MODERATE_SCHEDULE, schedule_id)
	if not schedules.pause(schedule_id, actor.id, "admin"):
		return jsonify(error=SCHEDULE_NOT_ACTIVE), 409
	return jsonify(message="The schedule was paused.")


# Resume a schedule that an administrator paused
@bp.post("/schedules/<int:schedule_id>/resume")
@login_required
def resume_schedule(schedule_id):
	actor = current_actor()
	authorized_schedule(actor, MODERATE_SCHEDULE, schedule_id)
	if not schedules.resume(schedule_id, actor.id, schedules.ADMIN_PAUSES):
		return jsonify(error=SCHEDULE_NOT_PAUSED), 409
	return jsonify(message="The schedule was resumed.")


# Cancel the schedule of any account
@bp.post("/schedules/<int:schedule_id>/cancel")
@login_required
def cancel_schedule(schedule_id):
	actor = current_actor()
	authorized_schedule(actor, MODERATE_SCHEDULE, schedule_id)
	if not schedules.cancel(schedule_id, actor.id):
		return jsonify(error=SCHEDULE_CANCELLED), 409
	return jsonify(message="The schedule was cancelled.")

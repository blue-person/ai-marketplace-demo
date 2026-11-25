# Import libraries
from flask import Blueprint, jsonify

# Import modules
from . import schedules
from .db import query
from .rbac import LIST_OWN_SCHEDULES, MANAGE_SCHEDULE, SCHEDULE_AGENT, require
from .security import authorized_schedule, key_or_session_actor, key_or_session_required, read_json_object

# Blueprint of the schedule routes
bp = Blueprint("schedules", __name__, url_prefix="/api/schedules")

# Constants
NOT_ACTIVE = "The schedule is not active."
NOT_RESUMABLE = "The schedule is not paused or an administrator paused it."
ALREADY_CANCELLED = "The schedule is already cancelled."


# Return the balance of the account as it is now
def _balance(account_id: int):
	return query("SELECT balance FROM accounts WHERE id = %s", (account_id,), one=True)["balance"]


# Schedule an agent that is recurring or conditional for the account of the request
@bp.post("")
@key_or_session_required
def create_schedule():
	actor = key_or_session_actor()
	require(actor, SCHEDULE_AGENT)
	schedule = schedules.validate_schedule(read_json_object())
	return jsonify(schedule_id=schedules.create(actor.id, schedule)), 201


# List the schedules of the account with the limits that the forms show
@bp.get("")
@key_or_session_required
def list_schedules():
	actor = key_or_session_actor()
	require(actor, LIST_OWN_SCHEDULES)
	return jsonify(schedules=schedules.own_schedules(actor.id), limits=schedules.LIMITS, balance=_balance(actor.id))


# Pause one schedule of the account
@bp.post("/<int:schedule_id>/pause")
@key_or_session_required
def pause_schedule(schedule_id):
	actor = key_or_session_actor()
	authorized_schedule(actor, MANAGE_SCHEDULE, schedule_id)
	if not schedules.pause(schedule_id, actor.id, "owner"):
		return jsonify(error=NOT_ACTIVE), 409
	return jsonify(message="The schedule was paused.")


# Resume one paused schedule of the account unless an administrator paused it
@bp.post("/<int:schedule_id>/resume")
@key_or_session_required
def resume_schedule(schedule_id):
	actor = key_or_session_actor()
	authorized_schedule(actor, MANAGE_SCHEDULE, schedule_id)
	if not schedules.resume(schedule_id, actor.id, schedules.OWNER_PAUSES):
		return jsonify(error=NOT_RESUMABLE), 409
	return jsonify(message="The schedule was resumed.")


# Cancel one schedule of the account for good
@bp.post("/<int:schedule_id>/cancel")
@key_or_session_required
def cancel_schedule(schedule_id):
	actor = key_or_session_actor()
	authorized_schedule(actor, MANAGE_SCHEDULE, schedule_id)
	if not schedules.cancel(schedule_id, actor.id):
		return jsonify(error=ALREADY_CANCELLED), 409
	return jsonify(message="The schedule was cancelled.")

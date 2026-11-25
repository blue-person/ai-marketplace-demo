# Import libraries
from flask import Blueprint, jsonify

# Import modules
from . import schedules
from .rbac import APPROVE_REGISTRATION, DISPATCH_SCHEDULES, LIST_REGISTRATIONS, require
from .registration import approve_account, pending_profiles
from .security import api_key_actor, api_key_required, authorized_target

# Blueprint of the routes used by the robots
bp = Blueprint("internal", __name__, url_prefix="/api/internal")

# Constants
NOT_PENDING = "The registration is not pending."
NOT_DUE = "The schedule is not due."


# List the pending registrations with only the fields the robot needs
@bp.get("/registrations")
@api_key_required
def list_registrations():
	require(api_key_actor(), LIST_REGISTRATIONS)
	return jsonify(registrations=pending_profiles())


# Approve one pending registration in the name of the robot
@bp.post("/registrations/<int:account_id>/approve")
@api_key_required
def approve_registration(account_id):
	actor = api_key_actor()
	authorized_target(actor, APPROVE_REGISTRATION, account_id)
	if not approve_account(account_id, actor.id):
		return jsonify(error=NOT_PENDING), 409
	return jsonify(message="The account was approved.")


# List the ids of the schedules that are due now
@bp.get("/schedules/due")
@api_key_required
def list_due_schedules():
	require(api_key_actor(), DISPATCH_SCHEDULES)
	return jsonify(schedules=[{"id": schedule_id} for schedule_id in schedules.due_ids()])


# Launch one schedule in the name of the dispatch robot when it is still due
@bp.post("/schedules/<int:schedule_id>/launch")
@api_key_required
def launch_schedule(schedule_id):
	actor = api_key_actor()
	require(actor, DISPATCH_SCHEDULES)
	outcome = schedules.launch(schedule_id, actor.id)
	if outcome is None:
		return jsonify(error=NOT_DUE), 409
	return jsonify(outcome=outcome)

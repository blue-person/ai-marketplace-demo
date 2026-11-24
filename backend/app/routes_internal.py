# Import libraries
from flask import Blueprint, jsonify

# Import modules
from .rbac import APPROVE_REGISTRATION, LIST_REGISTRATIONS, require
from .registration import approve_account, pending_profiles
from .security import api_key_actor, api_key_required, authorized_target

# Blueprint of the routes used by the robots
bp = Blueprint("internal", __name__, url_prefix="/api/internal")

# Constants
NOT_PENDING = "The registration is not pending."


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

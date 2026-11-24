# Import libraries
from flask import Blueprint, abort, jsonify, request

# Import modules
from .registration import REJECTION_REASONS, approve_account, pending_registrations, reject_account
from .security import current_user, role_required

# Blueprint of the administrator routes
bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# Constants
NOT_PENDING = "The registration is not pending."


# List the pending registrations and the reasons that can be used to reject one
@bp.get("/registrations")
@role_required("admin")
def list_registrations():
	reasons = [{"key": key, "label": label} for key, label in REJECTION_REASONS.items()]
	return jsonify(registrations=pending_registrations(), rejection_reasons=reasons)


# Approve one pending registration
@bp.post("/registrations/<int:account_id>/approve")
@role_required("admin")
def approve_registration(account_id):
	if not approve_account(account_id, current_user()["id"]):
		return jsonify(error=NOT_PENDING), 409
	return jsonify(message="The account was approved.")


# Reject one pending registration with a reason from the list
@bp.post("/registrations/<int:account_id>/reject")
@role_required("admin")
def reject_registration(account_id):
	data = request.get_json(silent=True) or {}
	reason = str(data.get("reason", ""))
	if reason not in REJECTION_REASONS:
		abort(400, description="The reason is not valid.")
	if not reject_account(account_id, current_user()["id"], reason):
		return jsonify(error=NOT_PENDING), 409
	return jsonify(message="The account was rejected.")

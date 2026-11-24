# Import libraries
from flask import Blueprint, abort, jsonify, request

# Import modules
from .accounts import LastAdminError, change_status, list_accounts
from .rbac import (
	APPROVE_REGISTRATION,
	LIST_ACCOUNTS,
	LIST_REGISTRATIONS,
	MANAGE_ACCOUNT_STATUS,
	REJECT_REGISTRATION,
	require,
)
from .registration import REJECTION_REASONS, approve_account, pending_registrations, reject_account
from .security import authorized_target, current_actor, login_required

# Blueprint of the administrator routes
bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# Constants
NOT_PENDING = "The registration is not pending."
STATUS_NOT_CHANGEABLE = "The account is not in the status that this action needs."
LAST_ADMIN = "The platform needs at least one active administrator."


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
	data = request.get_json(silent=True) or {}
	reason = str(data.get("reason", ""))
	if reason not in REJECTION_REASONS:
		abort(400, description="The reason is not valid.")
	if not reject_account(account_id, actor.id, reason):
		return jsonify(error=NOT_PENDING), 409
	return jsonify(message="The account was rejected.")


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

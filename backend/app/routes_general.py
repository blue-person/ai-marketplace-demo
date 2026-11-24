# Import libraries
from flask import Blueprint, abort, current_app, jsonify, request, session

# Import modules
from . import audit, external_api
from .countries import country_choices
from .db import query, retry_on_deadlock, transaction
from .passwords import PASSWORD_RULES
from .rbac import MANAGE_API_KEY, RENAME_ACCOUNT, VIEW_ACCOUNT
from .registration import MAX_NAME_LENGTH, regenerate_api_key
from .security import authorized_target, current_actor, login_required, read_json_object

# Blueprint of the general routes
bp = Blueprint("general", __name__, url_prefix="/api")

# Constants
PUBLIC_ACCOUNT_COLUMNS = "id, name, email, role, status, organization, country, created_at"
OWNER_ACCOUNT_COLUMNS = PUBLIC_ACCOUNT_COLUMNS + ", referral_code"


# Check that the database is reachable
@bp.get("/health")
def health():
	query("SELECT 1 AS ok", one=True)
	return jsonify(status="ok")


# Return the public settings of the active case
@bp.get("/config")
def public_config():
	case = current_app.config["CASE"]

	# Only the roles that the backend opens to the public are sent for the sign up form
	registration_roles = [
		{"key": key, "label": role["label"]} for key, role in case["roles"].items() if role["public_registration"]
	]
	return jsonify(
		case=case["key"],
		name=case["name"],
		registration_roles=registration_roles,
		countries=country_choices(),
		password_rules=PASSWORD_RULES,
		external_api=current_app.config["EXTERNAL_API_BASE_URL"],
	)


# Search active accounts by name
@bp.get("/directory")
def directory():
	term = request.args.get("q", "")

	# Send the whole pattern as one parameter and leave the robots out of the list
	results = query(
		"SELECT id, name, role FROM accounts WHERE status = 'active' AND role <> 'bot' AND name LIKE %s ORDER BY name",
		(f"%{term}%",),
	)
	return jsonify(results=results)


# Profile routes


# Read the profile of the owner with the code and the prefix of the key
def _owner_account(account_id: int) -> dict:
	account = query(f"SELECT {OWNER_ACCOUNT_COLUMNS} FROM accounts WHERE id = %s", (account_id,), one=True)
	key = query("SELECT key_prefix FROM api_keys WHERE account_id = %s", (account_id,), one=True)
	account["api_key_prefix"] = key["key_prefix"] if key else None
	return account


# Return the profile of one account to its owner or to an administrator
@bp.get("/accounts/<int:account_id>")
@login_required
def get_account(account_id):
	actor = current_actor()
	authorized_target(actor, VIEW_ACCOUNT, account_id)
	if account_id == actor.id:
		return jsonify(account=_owner_account(account_id))

	# An administrator sees the public columns of other accounts and never their codes
	account = query(f"SELECT {PUBLIC_ACCOUNT_COLUMNS} FROM accounts WHERE id = %s", (account_id,), one=True)
	return jsonify(account=account)


# Change the name in one transaction with the old name locked and repeat it after a deadlock
@retry_on_deadlock
def _rename_account(account_id: int, name: str) -> None:
	with transaction() as tx:
		old = tx.query("SELECT name FROM accounts WHERE id = %s FOR UPDATE", (account_id,), one=True)
		tx.execute("UPDATE accounts SET name = %s WHERE id = %s", (name, account_id))
		audit.record(
			tx, "account_renamed", "success", account_id, account_id, details={"from": old["name"], "to": name}
		)


# Update the name of the signed in account and nothing else
@bp.put("/accounts/<int:account_id>")
@login_required
def update_account(account_id):
	authorized_target(current_actor(), RENAME_ACCOUNT, account_id)
	data = read_json_object()
	name = str(data.get("name", "")).strip()
	if not name or len(name) > MAX_NAME_LENGTH:
		abort(400, description=f"The name must have between 1 and {MAX_NAME_LENGTH} characters.")
	_rename_account(account_id, name)
	return jsonify(account=_owner_account(account_id))


# Replace the API key of the signed in account and show the new one only once
@bp.post("/accounts/<int:account_id>/api-key")
@login_required
def create_api_key(account_id):
	authorized_target(current_actor(), MANAGE_API_KEY, account_id)
	api_key = regenerate_api_key(account_id)
	if api_key is None:
		abort(403, description="Only active accounts have an API key.")
	return jsonify(api_key=api_key.key, api_key_prefix=api_key.prefix), 201


# Call the external API or the url in the query string
@bp.get("/example/external-api")
@login_required
def external_api_example():
	case_key = current_app.config["CASE"]["key"]
	address = request.args.get("url")
	try:
		if address:
			response = external_api.get(address)
			return jsonify(status=response.status_code, content=response.text)

		# Serve heart rate samples when the case is healthsync
		if case_key == "healthsync":
			response = external_api.get(
				external_api.url("dataPoints"),
				params={"schema": "heart-rate", "user": session["account_id"], "days": 1},
			)
			return jsonify(source="Open mHealth (simulated)", samples=response.json()[:5])

		# Other cases call the simulated chat completion endpoint
		response = external_api.post(
			external_api.url("chat/completions"),
			{"model": "simulated/echo-1", "messages": [{"role": "user", "content": "Hello from the template"}]},
		)
		return jsonify(source="OpenRouter (simulated)", reply=response.json()["choices"][0]["message"]["content"])
	except external_api.ExternalApiError as error:
		return jsonify(error=f"The external API did not respond: {error}"), 502

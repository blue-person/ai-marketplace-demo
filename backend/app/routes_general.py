# Import libraries
from flask import Blueprint, abort, current_app, jsonify, request, session

# Import modules
from . import external_api
from .db import query, retry_on_deadlock, transaction
from .security import current_user, login_required

# Blueprint of the general routes
bp = Blueprint("general", __name__, url_prefix="/api")

# Constants
MAX_NAME_LENGTH = 120
PUBLIC_ACCOUNT_COLUMNS = "id, name, email, role, status, created_at"


# Check that the database is reachable
@bp.get("/health")
def health():
	query("SELECT 1 AS ok", one=True)
	return jsonify(status="ok")


# Return the public settings of the active case
@bp.get("/config")
def public_config():
	case = current_app.config["CASE"]
	return jsonify(
		case=case["key"],
		name=case["name"],
		roles=case["roles"],
		external_api=current_app.config["EXTERNAL_API_BASE_URL"],
	)


# Search active accounts by name
@bp.get("/directory")
def directory():
	term = request.args.get("q", "")

	# Send the whole pattern as one parameter
	results = query(
		"SELECT id, name, role FROM accounts WHERE status = 'active' AND name LIKE %s ORDER BY name",
		(f"%{term}%",),
	)
	return jsonify(results=results)


# Profile routes


# Return the profile of one account to its owner or to an administrator
@bp.get("/accounts/<int:account_id>")
@login_required
def get_account(account_id):
	user = current_user()
	if account_id != user["id"] and user["role"] != "admin":
		abort(403)
	account = query(f"SELECT {PUBLIC_ACCOUNT_COLUMNS} FROM accounts WHERE id = %s", (account_id,), one=True)
	if not account:
		abort(404)
	return jsonify(account=account)


# Change the name in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _rename_account(account_id: int, name: str) -> None:
	with transaction() as tx:
		tx.execute("UPDATE accounts SET name = %s WHERE id = %s", (name, account_id))


# Update the name of the signed in account and nothing else
@bp.put("/accounts/<int:account_id>")
@login_required
def update_account(account_id):
	if account_id != current_user()["id"]:
		abort(403)
	data = request.get_json(silent=True) or {}
	name = str(data.get("name", "")).strip()
	if not name or len(name) > MAX_NAME_LENGTH:
		abort(400, description=f"The name must have between 1 and {MAX_NAME_LENGTH} characters.")
	_rename_account(account_id, name)

	# Keep the name stored in the session in sync after a rename
	session["name"] = name
	account = query(f"SELECT {PUBLIC_ACCOUNT_COLUMNS} FROM accounts WHERE id = %s", (account_id,), one=True)
	return jsonify(account=account)


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

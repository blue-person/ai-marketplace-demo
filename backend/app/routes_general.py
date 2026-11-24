"""Support routes and examples: health, config, directory, profile and external API."""
from flask import Blueprint, abort, current_app, jsonify, request, session

from . import external_api
from .db import commit, execute, query
from .security import login_required

bp = Blueprint("general", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    query("SELECT 1 AS ok", one=True)
    return jsonify(status="ok")


@bp.get("/config")
def public_config():
    case = current_app.config["CASE"]
    return jsonify(
        case=case["key"],
        name=case["name"],
        roles=case["roles"],
        external_api=current_app.config["EXTERNAL_API_BASE_URL"],
    )


# ------------------------------------------------------------------ Directory
@bp.get("/directory")
def directory():
    """Searches active accounts by name. Example for the case's directory or catalog."""
    term = request.args.get("q", "")
    results = query(
        "SELECT id, name, role FROM accounts "
        f"WHERE status = 'active' AND name LIKE '%{term}%' ORDER BY name"
    )
    return jsonify(results=results)


# -------------------------------------------------------------------- Profile
@bp.get("/accounts/<int:account_id>")
@login_required
def get_account(account_id):
    account = query("SELECT * FROM accounts WHERE id = %s", (account_id,), one=True)
    if not account:
        abort(404)
    return jsonify(account=account)


@bp.put("/accounts/<int:account_id>")
@login_required
def update_account(account_id):
    data = request.get_json(silent=True) or {}
    if not data:
        abort(400, description="There is no data to update.")
    assignments = ", ".join(f"{field} = %s" for field in data)
    execute(f"UPDATE accounts SET {assignments} WHERE id = %s", (*data.values(), account_id))
    commit()
    if account_id == session.get("account_id") and "name" in data:
        session["name"] = data["name"]
    return jsonify(account=query("SELECT * FROM accounts WHERE id = %s", (account_id,), one=True))


# --------------------------------------------------------------- External API
@bp.get("/example/external-api")
@login_required
def external_api_example():
    """Queries the case's external API. Optionally receives the URL to query."""
    case_key = current_app.config["CASE"]["key"]
    address = request.args.get("url")
    try:
        if address:
            response = external_api.get(address)
            return jsonify(status=response.status_code, content=response.text)
        if case_key == "healthsync":
            response = external_api.get(
                external_api.url("dataPoints"),
                params={"schema": "heart-rate", "user": session["account_id"], "days": 1},
            )
            return jsonify(source="Open mHealth (simulated)", samples=response.json()[:5])
        response = external_api.post(
            external_api.url("chat/completions"),
            {"model": "simulated/echo-1", "messages": [{"role": "user", "content": "Hello from the template"}]},
        )
        return jsonify(source="OpenRouter (simulated)", reply=response.json()["choices"][0]["message"]["content"])
    except external_api.ExternalApiError as error:
        return jsonify(error=f"The external API did not respond: {error}"), 502

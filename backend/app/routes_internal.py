"""Internal endpoints for the C++ robot (the "worker" service).

Every request must carry the X-Internal-Token header with the WORKER_TOKEN value.
Add here the endpoints your robots need.
"""

from flask import Blueprint, Response, abort, current_app, request

from .db import query

bp = Blueprint("internal", __name__, url_prefix="/api/internal")


@bp.before_request
def verify_token():
	if request.headers.get("X-Internal-Token") != current_app.config["WORKER_TOKEN"]:
		abort(401)


@bp.get("/pending")
def pending():
	"""Accounts pending approval, one per line: id|name|email."""
	accounts = query("SELECT id, name, email FROM accounts WHERE status = 'pending' ORDER BY id")
	lines = [f"{a['id']}|{a['name']}|{a['email']}" for a in accounts]
	return Response("\n".join(lines) + ("\n" if lines else ""), mimetype="text/plain")

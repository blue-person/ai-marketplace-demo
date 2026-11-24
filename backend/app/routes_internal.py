# Import libraries
from flask import Blueprint, Response, abort, current_app, request

# Import modules
from .db import query

# Blueprint of the internal worker routes
bp = Blueprint("internal", __name__, url_prefix="/api/internal")


# Every request needs the worker token in the X-Internal-Token header
@bp.before_request
def verify_token():
	if request.headers.get("X-Internal-Token") != current_app.config["WORKER_TOKEN"]:
		abort(401)


# Return one line per pending account in the form id|name|email
@bp.get("/pending")
def pending():
	accounts = query("SELECT id, name, email FROM accounts WHERE status = 'pending' ORDER BY id")

	# Format each account as one pipe separated line
	lines = [f"{a['id']}|{a['name']}|{a['email']}" for a in accounts]

	# Add a final newline only when there are lines
	return Response("\n".join(lines) + ("\n" if lines else ""), mimetype="text/plain")

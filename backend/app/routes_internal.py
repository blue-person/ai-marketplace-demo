# Import libraries
import hmac
from flask import Blueprint, Response, abort, current_app, request

# Import modules
from .registration import approve_complete_profiles

# Blueprint of the internal worker routes
bp = Blueprint("internal", __name__, url_prefix="/api/internal")


# Every request needs the worker token in the X-Internal-Token header
@bp.before_request
def verify_token():
	expected = current_app.config["WORKER_TOKEN"]
	sent = request.headers.get("X-Internal-Token", "")

	# The comparison takes the same time wherever the texts differ
	if not expected or not hmac.compare_digest(sent.encode("utf-8"), expected.encode("utf-8")):
		abort(401)


# Approve the pending accounts with a complete profile and return how many were approved
@bp.post("/auto-approve")
def auto_approve():
	return Response(f"{approve_complete_profiles()}\n", mimetype="text/plain")

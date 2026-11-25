# Import libraries
from flask import Blueprint, abort, jsonify, request

# Import modules
from . import executions
from .db import query
from .money import NotEnoughBalanceError
from .rbac import EXECUTE_AGENT, LIST_OWN_EXECUTIONS, VIEW_AGENT_EARNINGS, require
from .security import current_actor, key_or_session_actor, key_or_session_required, login_required, read_json_object

# Blueprint of the execution routes
bp = Blueprint("executions", __name__, url_prefix="/api")

# Constants
NOT_ENOUGH_BALANCE = "The balance is not enough."
NOT_RUN = "The agent could not run and the price was returned to your balance."


# Return the balance of the account as it is now
def _balance(account_id: int):
	return query("SELECT balance FROM accounts WHERE id = %s", (account_id,), one=True)["balance"]


# Run an agent once and charge its price unless the signed in developer owns it
@bp.post("/agents/<int:agent_id>/executions")
@key_or_session_required
def execute_agent(agent_id):
	actor = key_or_session_actor()
	require(actor, EXECUTE_AGENT)
	key = executions.read_idempotency_key(request.headers.get("Idempotency-Key"))
	prompt = executions.read_prompt(read_json_object())
	try:
		execution, created = executions.run_execution(actor.id, agent_id, key, prompt)
	except NotEnoughBalanceError:
		return jsonify(error=NOT_ENOUGH_BALANCE), 402
	balance = _balance(actor.id)

	# The model failed and the credit is back, so the client gets the execution to show what happened
	if execution["status"] == "failed":
		return jsonify(error=NOT_RUN, execution=execution, balance=balance), 502
	return jsonify(execution=execution, balance=balance), 201 if created else 200


# List the latest executions of the account with a short summary of each one
@bp.get("/executions")
@key_or_session_required
def list_executions():
	actor = key_or_session_actor()
	require(actor, LIST_OWN_EXECUTIONS)
	executions.expire_stale(actor.id)
	return jsonify(executions=executions.own_executions(actor.id), balance=_balance(actor.id))


# Return one execution of the account with its full prompt and response
@bp.get("/executions/<int:execution_id>")
@key_or_session_required
def get_execution(execution_id):
	actor = key_or_session_actor()
	require(actor, LIST_OWN_EXECUTIONS)
	execution = executions.get_execution(actor.id, execution_id)
	if execution is None:
		abort(404, description="The execution was not found.")
	return jsonify(execution=execution)


# List what the agents of the signed in developer earned without the text of the users
@bp.get("/agents/mine/executions")
@login_required
def list_earnings():
	actor = current_actor()
	require(actor, VIEW_AGENT_EARNINGS)
	return jsonify(earnings=executions.agent_earnings(actor.id))

# Import libraries
from flask import Blueprint, abort, current_app, jsonify, request

# Import modules
from . import agents, external_api
from .db import DuplicateError
from .rbac import LIST_OWN_AGENTS, PUBLISH_AGENT, VIEW_CATALOG, require
from .security import current_actor, login_required, read_json_object

# Blueprint of the agent routes
bp = Blueprint("agents", __name__, url_prefix="/api/agents")

# Constants
DUPLICATE_NAME = "You already have an agent with that name."
MODELS_UNAVAILABLE = "The list of models is not available now."


# Categories as a list of keys and labels for the forms
def _category_options() -> list[dict]:
	return [{"key": key, "label": label} for key, label in agents.CATEGORIES.items()]


# Read the models of the external API and answer with a 502 when it does not respond
def _read_models() -> list[str]:
	try:
		return external_api.list_models()
	except external_api.ExternalApiError as error:
		current_app.logger.warning("The models could not be read: %s", error)
		abort(502, description=MODELS_UNAVAILABLE)


# List the approved agents and narrow them to one category when it is given
@bp.get("")
@login_required
def list_catalog():
	require(current_actor(), VIEW_CATALOG)
	category = request.args.get("category") or None
	if category is not None and category not in agents.CATEGORIES:
		abort(400, description="The category is not valid.")
	return jsonify(agents=agents.catalog(category), categories=_category_options())


# Return the categories and the models that a publication can use
@bp.get("/options")
@login_required
def publish_options():
	require(current_actor(), PUBLISH_AGENT)
	return jsonify(categories=_category_options(), models=_read_models())


# List the agents of the signed in developer in every status
@bp.get("/mine")
@login_required
def list_own_agents():
	actor = current_actor()
	require(actor, LIST_OWN_AGENTS)
	return jsonify(agents=agents.own_agents(actor.id))


# Publish an agent that stays pending until an administrator reviews it
@bp.post("")
@login_required
def publish_agent():
	actor = current_actor()
	require(actor, PUBLISH_AGENT)

	# The models are read before the transaction because a call to another service never runs inside one
	models = _read_models()
	agent = agents.validate_submission(read_json_object(), models)
	try:
		agent_id = agents.submit_agent(actor.id, agent)
	except DuplicateError:
		return jsonify(error=DUPLICATE_NAME), 409
	return jsonify(agent_id=agent_id, message="The agent was sent for review."), 201

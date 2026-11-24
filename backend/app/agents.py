# Import libraries
from decimal import Decimal
from urllib.parse import urlsplit
from flask import abort

# Import modules
from . import audit
from .db import query, retry_on_deadlock, transaction
from .money import parse_usd

# Constants
MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 1000
MAX_ENDPOINT_LENGTH = 500
MAX_PRICE = Decimal("1000.00")
ENDPOINT_SCHEMES = ("http", "https")
CATEGORIES = {
	"writing": "Writing",
	"coding": "Coding",
	"data": "Data analysis",
	"support": "Customer support",
	"research": "Research",
	"other": "Other",
}
REJECTION_REASONS = {
	"inappropriate_content": "Inappropriate content",
	"unclear_description": "Unclear description",
	"invalid_endpoint": "Invalid test endpoint",
	"duplicate_agent": "Duplicate agent",
	"other": "Other",
}


# Read a text field of the request and refuse a value that is missing, empty or too long
def _read_text(data: dict, key: str, label: str, max_length: int) -> str:
	value = data.get(key)
	if not isinstance(value, str) or not value.strip():
		abort(400, description=f"The {label} is required.")
	text = value.strip()
	if len(text) > max_length:
		abort(400, description=f"The {label} must have at most {max_length} characters.")
	return text


# True when the text is an http or https address with a host and without credentials
def is_valid_endpoint(endpoint: str) -> bool:
	if any(char.isspace() for char in endpoint) or not endpoint.isprintable():
		return False

	# Reading the port raises an error when it is not a number or is out of range
	try:
		parts = urlsplit(endpoint)
		port_is_valid = parts.port != 0
	except ValueError:
		return False
	return parts.scheme in ENDPOINT_SCHEMES and bool(parts.hostname) and "@" not in parts.netloc and port_is_valid


# Check every field of a publication and return the clean values or stop with a 400
def validate_submission(data: dict, allowed_models: list[str]) -> dict:
	name = _read_text(data, "name", "name", MAX_NAME_LENGTH)
	if not name.isprintable():
		abort(400, description="The name has characters that are not allowed.")
	description = _read_text(data, "description", "description", MAX_DESCRIPTION_LENGTH)
	price = parse_usd(data.get("price_usd"), MAX_PRICE, "price")

	# The type is checked first because a list cannot be looked up in a dictionary
	category = data.get("category")
	if not isinstance(category, str) or category not in CATEGORIES:
		abort(400, description="The category is not valid.")
	endpoint = _read_text(data, "test_endpoint", "test endpoint", MAX_ENDPOINT_LENGTH)
	if not is_valid_endpoint(endpoint):
		abort(400, description="The test endpoint must be an http or https address without credentials.")
	model = data.get("model")
	if not isinstance(model, str) or model not in allowed_models:
		abort(400, description="The model is not available.")
	return {
		"name": name,
		"description": description,
		"price_usd": price,
		"category": category,
		"test_endpoint": endpoint,
		"model": model,
	}


# Save a new agent as pending and its event in one transaction and repeat it after a deadlock
@retry_on_deadlock
def submit_agent(developer_id: int, agent: dict) -> int:
	with transaction() as tx:
		agent_id = tx.insert(
			"INSERT INTO agents (developer_id, name, description, price_usd, category, test_endpoint, model) "
			"VALUES (%s, %s, %s, %s, %s, %s, %s)",
			(
				developer_id,
				agent["name"],
				agent["description"],
				agent["price_usd"],
				agent["category"],
				agent["test_endpoint"],
				agent["model"],
			),
		)
		audit.record(
			tx,
			"agent_submitted",
			"success",
			developer_id,
			developer_id,
			details={"agent_id": agent_id, "name": agent["name"]},
		)
		return agent_id


# Move a pending agent to its final status and record the event in one transaction
@retry_on_deadlock
def _review(agent_id: int, reviewer_id: int, status: str, reason: str | None) -> bool:

	# The condition on the status in the update makes a second review change nothing
	with transaction() as tx:
		changed = tx.execute(
			"UPDATE agents SET status = %s, rejection_reason = %s, reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP "
			"WHERE id = %s AND status = 'pending'",
			(status, reason, reviewer_id, agent_id),
		)
		if not changed:
			return False

		# The row is locked by the update, so the name and the developer are the ones that were reviewed
		agent = tx.query("SELECT developer_id, name FROM agents WHERE id = %s", (agent_id,), one=True)
		details = {"agent_id": agent_id, "name": agent["name"]}
		if reason is not None:
			details["reason"] = reason
		audit.record(tx, f"agent_{status}", "success", reviewer_id, agent["developer_id"], details=details)
		return True


# Approve a pending agent and return False when it is not pending
def approve_agent(agent_id: int, reviewer_id: int) -> bool:
	return _review(agent_id, reviewer_id, "approved", None)


# Reject a pending agent with a reason of the list and return False when it is not pending
def reject_agent(agent_id: int, reviewer_id: int, reason: str) -> bool:
	return _review(agent_id, reviewer_id, "rejected", reason)


# True when an agent with that id exists in any status
def agent_exists(agent_id: int) -> bool:
	return query("SELECT id FROM agents WHERE id = %s", (agent_id,), one=True) is not None


# List the approved agents without the test endpoint and narrow them to one category when it is given
def catalog(category: str | None = None) -> list[dict]:

	# The condition is a fixed text and the category travels as a parameter
	where = "WHERE a.status = 'approved'" + (" AND a.category = %s" if category else "")
	params = (category,) if category else ()
	return query(
		"SELECT a.id, a.name, a.description, a.price_usd, a.category, a.model, d.name AS developer_name "
		f"FROM agents a JOIN accounts d ON d.id = a.developer_id {where} ORDER BY a.name, a.id",
		params,
	)


# List the agents of one developer in every status with the label of the rejection reason
def own_agents(developer_id: int) -> list[dict]:
	rows = query(
		"SELECT id, name, description, price_usd, category, test_endpoint, model, status, rejection_reason, created_at "
		"FROM agents WHERE developer_id = %s ORDER BY id DESC",
		(developer_id,),
	)
	for row in rows:
		row["rejection_label"] = REJECTION_REASONS.get(row["rejection_reason"])
	return rows


# List the pending agents with their developer for the administrators
def pending_agents() -> list[dict]:
	return query(
		"SELECT a.id, a.name, a.description, a.price_usd, a.category, a.test_endpoint, a.model, a.created_at, "
		"d.name AS developer_name, d.email AS developer_email "
		"FROM agents a JOIN accounts d ON d.id = a.developer_id WHERE a.status = 'pending' ORDER BY a.id"
	)

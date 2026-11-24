# Import libraries
from decimal import Decimal
import pytest
from werkzeug.exceptions import BadRequest

# Import modules
from app import agents

# Constants
MODELS = ["simulated/echo-1", "simulated/summary-1"]
VALID = {
	"name": "Summarizer",
	"description": "Summarizes long texts.",
	"price_usd": "0.50",
	"category": "writing",
	"test_endpoint": "https://summarizer.example.test/health",
	"model": "simulated/summary-1",
}


# Copy of a valid publication with some fields changed
def _data(**changes) -> dict:
	return {**VALID, **changes}


# A valid publication returns the clean values with the price as a Decimal
def test_a_valid_publication_returns_the_clean_values():
	clean = agents.validate_submission(_data(name="  Summarizer  "), MODELS)
	assert clean == {**VALID, "price_usd": Decimal("0.50")}
	assert isinstance(clean["price_usd"], Decimal)


# A field that is missing or is not a text is refused with a 400
@pytest.mark.parametrize("field", ["name", "description", "test_endpoint"])
@pytest.mark.parametrize("value", [None, "", "   ", 5, ["a"], {"a": 1}])
def test_a_text_field_that_is_missing_or_not_a_text_is_refused(field, value):
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(**{field: value}), MODELS)


# A field that is absent from the body is refused with a 400
@pytest.mark.parametrize("field", list(VALID))
def test_an_absent_field_is_refused(field):
	data = _data()
	del data[field]
	with pytest.raises(BadRequest):
		agents.validate_submission(data, MODELS)


# The length limits are accepted at the limit and refused one character after it
@pytest.mark.parametrize(
	"field, limit",
	[("name", agents.MAX_NAME_LENGTH), ("description", agents.MAX_DESCRIPTION_LENGTH)],
)
def test_the_length_limits_are_exact(field, limit):
	assert agents.validate_submission(_data(**{field: "a" * limit}), MODELS)[field] == "a" * limit
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(**{field: "a" * (limit + 1)}), MODELS)


# The name cannot hold control characters but the description can have line breaks
def test_the_name_refuses_control_characters_and_the_description_keeps_line_breaks():
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(name="Line\nbreak"), MODELS)
	assert agents.validate_submission(_data(description="One\nTwo"), MODELS)["description"] == "One\nTwo"


# Prices outside the range or with more than two decimals are refused
@pytest.mark.parametrize("price", ["0", "0.00", "-1", "0.001", "1000.01", "abc", "NaN", "Infinity", None, True, [1]])
def test_a_price_outside_the_rule_is_refused(price):
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(price_usd=price), MODELS)


# The price limits are accepted and a number is read the same as a text
@pytest.mark.parametrize("price, expected", [("0.01", "0.01"), ("1000.00", "1000.00"), (5, "5"), (0.5, "0.5")])
def test_the_price_limits_are_accepted(price, expected):
	assert agents.validate_submission(_data(price_usd=price), MODELS)["price_usd"] == Decimal(expected)


# A category that is not in the list or is not a text is refused
@pytest.mark.parametrize("category", ["unknown", "", None, 5, ["writing"], {"a": 1}])
def test_a_category_outside_the_list_is_refused(category):
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(category=category), MODELS)


# A model that the external API does not offer or is not a text is refused
@pytest.mark.parametrize("model", ["unknown/model", "", None, 5, ["simulated/echo-1"]])
def test_a_model_outside_the_list_is_refused(model):
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(model=model), MODELS)


# Addresses with a scheme other than http or https are refused
@pytest.mark.parametrize(
	"endpoint",
	[
		"javascript:alert(1)",
		"file:///etc/passwd",
		"data:text/html,x",
		"ftp://host.test/x",
		"gopher://host.test",
		"//host.test/x",
		"host.test/x",
		"http:///path",
		"http://",
	],
)
def test_an_endpoint_with_another_scheme_or_without_host_is_refused(endpoint):
	assert agents.is_valid_endpoint(endpoint) is False


# Credentials in the address, white space, control characters and bad ports are refused
@pytest.mark.parametrize(
	"endpoint",
	[
		"http://user:pass@host.test/",
		"http://user@host.test/",
		"http://@host.test/",
		"http://host.test/a b",
		"http://host.test/\n",
		"http://host.test/\x00",
		"http://host.test:0/",
		"http://host.test:99999/",
		"http://host.test:abc/",
		"http://[::1/",
	],
)
def test_an_endpoint_with_credentials_spaces_or_a_bad_port_is_refused(endpoint):
	assert agents.is_valid_endpoint(endpoint) is False


# Addresses with a host are accepted and the backend only stores them
@pytest.mark.parametrize(
	"endpoint",
	[
		"http://agent.example.test",
		"https://agent.example.test/path?x=1",
		"https://agent.example.test:8443/path",
		"HTTPS://AGENT.EXAMPLE.TEST/",
		"http://127.0.0.1:9000/health",
	],
)
def test_an_http_or_https_address_with_a_host_is_accepted(endpoint):
	assert agents.is_valid_endpoint(endpoint) is True


# An address longer than the column is refused with a 400
def test_an_endpoint_longer_than_the_limit_is_refused():
	long_endpoint = "https://agent.example.test/" + "a" * agents.MAX_ENDPOINT_LENGTH
	with pytest.raises(BadRequest):
		agents.validate_submission(_data(test_endpoint=long_endpoint), MODELS)


# Every category and reason has a label to show
def test_every_category_and_reason_has_a_label():
	assert all(agents.CATEGORIES.values()) and all(agents.REJECTION_REASONS.values())
	assert "other" in agents.CATEGORIES and "other" in agents.REJECTION_REASONS


# Transaction double that answers the update and the read of the agent
class FakeTransaction:
	def __init__(self, changed):
		self.changed = changed
		self.executed = []
		self.inserts = []

	def execute(self, sql, params=()):
		self.executed.append((sql, params))
		return self.changed

	def query(self, sql, params=(), one=False):
		return {"developer_id": 3, "name": "Summarizer"}

	def insert(self, sql, params=()):
		self.inserts.append((sql, params))
		return 1


# Replace the transaction helper of the module with the double
def _use(monkeypatch, tx):
	class Context:
		def __enter__(self):
			return tx

		def __exit__(self, *args):
			return False

	monkeypatch.setattr(agents, "transaction", Context)


# The update only touches a pending agent and records the event with the developer as the target
def test_approving_updates_only_a_pending_agent_and_records_the_event(monkeypatch):
	tx = FakeTransaction(changed=1)
	_use(monkeypatch, tx)
	assert agents.approve_agent(7, 1) is True
	sql, params = tx.executed[0]
	assert "WHERE id = %s AND status = 'pending'" in sql
	assert params == ("approved", None, 1, 7)
	_sql, event = tx.inserts[0]
	assert event[1:5] == ("agent_approved", "success", 1, 3)


# A review that changes no row records nothing and returns False
@pytest.mark.parametrize("review", [lambda: agents.approve_agent(7, 1), lambda: agents.reject_agent(7, 1, "other")])
def test_a_review_that_changes_no_row_records_nothing(monkeypatch, review):
	tx = FakeTransaction(changed=0)
	_use(monkeypatch, tx)
	assert review() is False
	assert tx.inserts == []


# A rejection stores the reason in the row and in the event
def test_rejecting_stores_the_reason_in_the_row_and_in_the_event(monkeypatch):
	tx = FakeTransaction(changed=1)
	_use(monkeypatch, tx)
	assert agents.reject_agent(7, 1, "invalid_endpoint") is True
	assert tx.executed[0][1] == ("rejected", "invalid_endpoint", 1, 7)
	_sql, event = tx.inserts[0]
	assert event[1:5] == ("agent_rejected", "success", 1, 3)
	assert '"reason": "invalid_endpoint"' in event[-1]


# The publication saves the agent as pending and records who sent it
def test_submitting_records_the_event_with_the_developer(monkeypatch):
	tx = FakeTransaction(changed=1)
	_use(monkeypatch, tx)
	clean = agents.validate_submission(_data(), MODELS)
	assert agents.submit_agent(3, clean) == 1
	assert "status" not in tx.inserts[0][0].split("VALUES")[0]
	assert tx.inserts[0][1][0] == 3
	assert tx.inserts[1][1][1:5] == ("agent_submitted", "success", 3, 3)

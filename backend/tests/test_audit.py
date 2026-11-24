# Import libraries
import json
import re
from decimal import Decimal
from pathlib import Path
import pytest
from mysql.connector import errors

# Import modules
from app import audit

# Constants
SCHEMA = Path(__file__).resolve().parents[2] / "database" / "init" / "05-audit.sql"


# Transaction double that keeps the statements it receives
class FakeTransaction:
	def __init__(self):
		self.inserts = []

	def insert(self, sql, params=()):
		self.inserts.append((sql, params))
		return 1


# The category of an event comes from its action and nobody passes it
def test_record_stores_the_category_of_the_action():
	tx = FakeTransaction()
	audit.record(tx, "authn_login_fail", "failure", None, target_label="a@b.test")
	_sql, params = tx.inserts[0]
	assert params[:3] == ("authn", "authn_login_fail", "failure")


# An action that is not in the list is a mistake of the code and not an event
def test_record_refuses_an_unknown_action():
	tx = FakeTransaction()
	with pytest.raises(ValueError):
		audit.record(tx, "made_up_action", "success", 1)
	assert tx.inserts == []


# An outcome other than success or failure cannot be stored
def test_record_refuses_an_unknown_outcome():
	with pytest.raises(ValueError):
		audit.record(FakeTransaction(), "authn_logout", "maybe", 1)


# A Decimal amount is stored as text because JSON has no decimal type
def test_record_stores_a_decimal_amount_as_text():
	tx = FakeTransaction()
	audit.record(tx, "credit_transfer", "success", 1, 2, details={"amount": Decimal("5.00")})
	assert json.loads(tx.inserts[0][1][-1]) == {"amount": "5.00"}


# An event without details stores NULL and not the text null
def test_record_stores_no_details_as_null():
	tx = FakeTransaction()
	audit.record(tx, "authn_logout", "success", 1)
	assert tx.inserts[0][1][-1] is None


# A failure of the database does not break the request that wanted to write the event
def test_record_alone_does_not_raise_when_the_database_fails(monkeypatch):
	def broken_transaction():
		raise errors.DatabaseError(msg="down", errno=2003)

	monkeypatch.setattr(audit, "transaction", broken_transaction)
	audit.record_alone("authz_fail", "failure", 1)


# A mistake of the code is not hidden by the rule that the log never stops a request
def test_record_alone_still_refuses_an_unknown_action():
	with pytest.raises(ValueError):
		audit.record_alone("made_up_action", "success", 1)


# Without filters the query has no WHERE and only the page size as parameter
def test_list_events_without_filters_has_no_where(monkeypatch):
	calls = []
	monkeypatch.setattr(audit, "query", lambda sql, params=(), one=False: calls.append((sql, params)) or [])
	audit.list_events()
	sql, params = calls[0]
	assert "WHERE" not in sql
	assert params == (audit.PAGE_SIZE,)


# A filter value travels as a parameter and never inside the SQL text
def test_list_events_sends_the_filter_as_a_parameter(monkeypatch):
	calls = []
	monkeypatch.setattr(audit, "query", lambda sql, params=(), one=False: calls.append((sql, params)) or [])
	audit.list_events(category="x' OR '1'='1")
	sql, params = calls[0]
	assert "x' OR" not in sql
	assert params == ("x' OR '1'='1", audit.PAGE_SIZE)


# The email of an account matches the actor, the target and the email typed in a failed login
def test_list_events_filters_an_account_by_email_on_the_three_columns(monkeypatch):
	calls = []
	monkeypatch.setattr(audit, "query", lambda sql, params=(), one=False: calls.append((sql, params)) or [])
	audit.list_events(account_email="a@b.test")
	sql, params = calls[0]
	assert "actor.email = %s" in sql and "target.email = %s" in sql and "e.target_label = %s" in sql
	assert params == ("a@b.test", "a@b.test", "a@b.test", audit.PAGE_SIZE)


# Two filters are joined with AND and keep the order of their values
def test_list_events_joins_the_filters_with_and(monkeypatch):
	calls = []
	monkeypatch.setattr(audit, "query", lambda sql, params=(), one=False: calls.append((sql, params)) or [])
	audit.list_events(category="authn", before_id=40)
	sql, params = calls[0]
	assert "e.category = %s AND e.id < %s" in sql
	assert params == ("authn", 40, audit.PAGE_SIZE)


# The details come back as a dictionary and not as JSON text
def test_list_events_returns_the_details_as_a_dictionary(monkeypatch):
	rows = [{"id": 1, "details": '{"from": "A", "to": "B"}'}]
	monkeypatch.setattr(audit, "query", lambda sql, params=(), one=False: rows)
	assert audit.list_events()[0]["details"] == {"from": "A", "to": "B"}


# The categories of the code and the ones of the table must be the same list
def test_every_category_of_the_code_exists_in_the_table():
	enum = re.search(r"category\s+ENUM\(([^)]*)\)", SCHEMA.read_text()).group(1)
	table_categories = set(re.findall(r"'(\w+)'", enum))
	assert set(audit.ACTIONS.values()) == table_categories

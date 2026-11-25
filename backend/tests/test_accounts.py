# Import libraries
import pytest

# Import modules
from app import accounts
from app.accounts import LastAdminError, _keep_one_admin
from app.rbac import Actor


# Transaction that answers the list of active administrators
class FakeTransaction:
	def __init__(self, admin_ids):
		self.admin_ids = admin_ids

	def query(self, sql, params=(), one=False):
		return [{"id": admin_id} for admin_id in self.admin_ids]


# The only active administrator cannot be suspended
def test_the_only_active_admin_cannot_be_suspended():
	with pytest.raises(LastAdminError):
		_keep_one_admin(FakeTransaction([1]), 1)


# An administrator can be suspended when another one stays active
def test_an_admin_can_be_suspended_when_another_admin_stays_active():
	assert _keep_one_admin(FakeTransaction([1, 2]), 1) is None


# Any other account can be suspended even when there is one administrator
def test_a_non_admin_account_can_be_suspended_with_a_single_admin():
	assert _keep_one_admin(FakeTransaction([1]), 7) is None


# Constants
ROWS = [
	{
		"id": 2,
		"name": "A",
		"email": "a@x.test",
		"role": "developer",
		"status": "active",
		"organization": None,
		"country": None,
		"created_at": "t",
	},
	{
		"id": 3,
		"name": "B",
		"email": "b@x.test",
		"role": "company",
		"status": "active",
		"organization": None,
		"country": None,
		"created_at": "t",
	},
]


# List the accounts of the fake database with a lock on the first one
def _list(monkeypatch, actor):
	monkeypatch.setattr(accounts, "query", lambda sql, params=(), one=False: ROWS)
	monkeypatch.setattr(accounts.login_throttle, "locks_of", lambda emails: {"a@x.test": "later"})
	return {row["email"]: row for row in accounts.list_accounts(actor)}


# An administrator can unlock only the accounts that are locked and sees when the lock ends
def test_an_admin_sees_the_locked_accounts_and_can_unlock_them(monkeypatch):
	listed = _list(monkeypatch, Actor(1, "admin", "active"))
	assert listed["a@x.test"]["locked_until"] == "later"
	assert listed["a@x.test"]["can_unlock"] is True
	assert listed["b@x.test"]["locked_until"] is None
	assert listed["b@x.test"]["can_unlock"] is False


# Unlocking uses the email stored in the account and the administrator that did it
def test_unlock_uses_the_stored_email(monkeypatch):
	calls = []
	monkeypatch.setattr(accounts, "query", lambda sql, params=(), one=False: {"email": "a@x.test"})
	monkeypatch.setattr(accounts.login_throttle, "unlock", lambda *args: calls.append(args) or True)
	assert accounts.unlock_account(2, 1) is True
	assert calls == [("a@x.test", 2, 1)]

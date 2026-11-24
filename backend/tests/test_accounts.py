# Import libraries
import pytest

# Import modules
from app.accounts import LastAdminError, _keep_one_admin


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

# Import libraries
import pytest
from flask import Flask
from werkzeug.exceptions import Forbidden

# Import modules
from app.rbac import (
	APPROVE_REGISTRATION,
	LIST_ACCOUNTS,
	LIST_REGISTRATIONS,
	MANAGE_ACCOUNT_STATUS,
	MANAGE_API_KEY,
	PLATFORM,
	RECEIVE_CREDIT,
	REJECT_REGISTRATION,
	RENAME_ACCOUNT,
	SEND_CREDIT,
	SIGN_IN,
	VIEW_ACCOUNT,
	AccountTarget,
	Actor,
	can,
	require,
)

# Constants
ADMIN = Actor(1, "admin", "active")
BOT = Actor(2, "bot", "active")
DEVELOPER = Actor(3, "developer", "active")
OTHER_DEVELOPER = Actor(4, "developer", "active")
SUSPENDED_ADMIN = Actor(1, "admin", "suspended")
COMPLETE = AccountTarget(10, "company", "pending", "Acme Labs", "CO")
NO_ORGANIZATION = AccountTarget(11, "company", "pending", None, "CO")
NO_COUNTRY = AccountTarget(12, "company", "pending", "Acme Labs", None)
DEVELOPER_ACCOUNT = AccountTarget(3, "developer", "active", "Dev Studio", "CO")
BOT_ACCOUNT = AccountTarget(2, "bot", "active", None, None)
ADMIN_ACCOUNT = AccountTarget(1, "admin", "active", None, None)
OTHER_ACCOUNT = AccountTarget(20, "company", "active", "Acme Labs", "CO")


# An administrator approves a pending account even when its profile is incomplete
def test_admin_approves_an_account_with_an_incomplete_profile():
	assert can(ADMIN, APPROVE_REGISTRATION, NO_ORGANIZATION) is True


# The robot approves an account when the profile is complete
def test_bot_approves_an_account_with_a_complete_profile():
	assert can(BOT, APPROVE_REGISTRATION, COMPLETE) is True


# The robot refuses an account that has no organization
def test_bot_cannot_approve_an_account_without_organization():
	assert can(BOT, APPROVE_REGISTRATION, NO_ORGANIZATION) is False


# The robot refuses an account that has no country
def test_bot_cannot_approve_an_account_without_country():
	assert can(BOT, APPROVE_REGISTRATION, NO_COUNTRY) is False


# A developer cannot approve any account
def test_developer_cannot_approve_an_account():
	assert can(DEVELOPER, APPROVE_REGISTRATION, COMPLETE) is False


# The robot can read the pending registrations and a developer cannot
def test_only_the_robot_and_the_admin_read_the_pending_registrations():
	assert can(BOT, LIST_REGISTRATIONS) is True
	assert can(DEVELOPER, LIST_REGISTRATIONS) is False


# An account that is not active can do nothing even when it is an administrator
def test_a_suspended_admin_cannot_list_registrations():
	assert can(SUSPENDED_ADMIN, LIST_REGISTRATIONS) is False


# The robot has no permission outside the approval flow
@pytest.mark.parametrize("action", [LIST_ACCOUNTS, SIGN_IN, SEND_CREDIT])
def test_bot_is_refused_the_platform_actions_outside_the_approval_flow(action):
	assert can(BOT, action) is False


# The robot cannot touch accounts even its own
@pytest.mark.parametrize("action", [REJECT_REGISTRATION, VIEW_ACCOUNT, RENAME_ACCOUNT, MANAGE_API_KEY])
def test_bot_is_refused_the_account_actions_even_on_its_own_account(action):
	assert can(BOT, action, BOT_ACCOUNT) is False


# People can sign in and the robot cannot
def test_a_developer_signs_in_and_the_robot_does_not():
	assert can(DEVELOPER, SIGN_IN) is True
	assert can(BOT, SIGN_IN) is False


# The owner reads and renames the own account
def test_owner_views_and_renames_the_own_account():
	assert can(DEVELOPER, VIEW_ACCOUNT, DEVELOPER_ACCOUNT) is True
	assert can(DEVELOPER, RENAME_ACCOUNT, DEVELOPER_ACCOUNT) is True


# Another developer cannot read the account
def test_developer_cannot_view_the_account_of_another_user():
	assert can(OTHER_DEVELOPER, VIEW_ACCOUNT, DEVELOPER_ACCOUNT) is False


# An administrator reads any account but cannot rename it
def test_admin_views_but_does_not_rename_the_account_of_another_user():
	assert can(ADMIN, VIEW_ACCOUNT, DEVELOPER_ACCOUNT) is True
	assert can(ADMIN, RENAME_ACCOUNT, DEVELOPER_ACCOUNT) is False


# The owner manages the key and another user does not
def test_only_the_owner_manages_the_api_key():
	assert can(DEVELOPER, MANAGE_API_KEY, DEVELOPER_ACCOUNT) is True
	assert can(ADMIN, MANAGE_API_KEY, DEVELOPER_ACCOUNT) is False


# Developers and companies send credit and an administrator does not
def test_a_developer_sends_credit_and_an_admin_does_not():
	assert can(DEVELOPER, SEND_CREDIT) is True
	assert can(ADMIN, SEND_CREDIT) is False


# Credit goes only to developers and companies
def test_credit_cannot_be_sent_to_a_robot_or_an_admin():
	assert can(DEVELOPER, RECEIVE_CREDIT, COMPLETE) is True
	assert can(DEVELOPER, RECEIVE_CREDIT, BOT_ACCOUNT) is False
	assert can(DEVELOPER, RECEIVE_CREDIT, ADMIN_ACCOUNT) is False


# An administrator changes the status of another account
def test_admin_suspends_the_account_of_another_user():
	assert can(ADMIN, MANAGE_ACCOUNT_STATUS, DEVELOPER_ACCOUNT) is True


# An administrator cannot suspend the own account
def test_admin_cannot_suspend_the_own_account():
	assert can(ADMIN, MANAGE_ACCOUNT_STATUS, ADMIN_ACCOUNT) is False


# Nobody but an administrator changes a status
@pytest.mark.parametrize("actor", [DEVELOPER, BOT])
def test_only_an_admin_changes_the_status_of_an_account(actor):
	assert can(actor, MANAGE_ACCOUNT_STATUS, OTHER_ACCOUNT) is False


# An action without rules is denied
def test_an_unknown_action_is_denied():
	assert can(ADMIN, "delete_everything") is False


# The library matches the exact type of the resource, so a dictionary is denied
def test_a_resource_of_a_type_without_rules_is_denied():
	assert can(ADMIN, APPROVE_REGISTRATION, {"id": 10, "status": "pending"}) is False


# A denied request is refused with a 403
def test_require_refuses_the_request_with_a_403():
	with Flask("test").app_context(), pytest.raises(Forbidden):
		require(DEVELOPER, APPROVE_REGISTRATION, COMPLETE)


# A permitted request goes through without an error
def test_require_lets_a_permitted_request_through():
	with Flask("test").app_context():
		assert require(ADMIN, APPROVE_REGISTRATION, COMPLETE) is None


# The platform marker is the default resource of the actions that act on no account
def test_the_platform_marker_is_the_default_resource():
	assert can(ADMIN, LIST_ACCOUNTS, PLATFORM) is True

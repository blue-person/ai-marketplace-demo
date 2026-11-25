# Import libraries
import pytest
from flask import Flask
from werkzeug.exceptions import Forbidden

# Import modules
from app import audit
from app.rbac import (
	APPROVE_REGISTRATION,
	EXECUTE_AGENT,
	LIST_ACCOUNTS,
	LIST_OWN_AGENTS,
	LIST_OWN_EXECUTIONS,
	LIST_REGISTRATIONS,
	MANAGE_ACCOUNT_STATUS,
	MANAGE_API_KEY,
	PLATFORM,
	PUBLISH_AGENT,
	RECEIVE_CREDIT,
	REJECT_REGISTRATION,
	RENAME_ACCOUNT,
	REVIEW_AGENTS,
	SEND_CREDIT,
	SIGN_IN,
	UNLOCK_ACCOUNT,
	VIEW_ACCOUNT,
	VIEW_AGENT_EARNINGS,
	VIEW_AUDIT,
	VIEW_CATALOG,
	VIEW_EXECUTIONS,
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
COMPANY = Actor(5, "company", "active")
SUSPENDED_ADMIN = Actor(1, "admin", "suspended")
SUSPENDED_DEVELOPER = Actor(3, "developer", "suspended")
COMPLETE = AccountTarget(10, "company", "pending", "Acme Labs", "CO")
NO_ORGANIZATION = AccountTarget(11, "company", "pending", None, "CO")
NO_COUNTRY = AccountTarget(12, "company", "pending", "Acme Labs", None)
DEVELOPER_ACCOUNT = AccountTarget(3, "developer", "active", "Dev Studio", "CO")
BOT_ACCOUNT = AccountTarget(2, "bot", "active", None, None)
ADMIN_ACCOUNT = AccountTarget(1, "admin", "active", None, None)
OTHER_ACCOUNT = AccountTarget(20, "company", "active", "Acme Labs", "CO")
SYSTEM_ACCOUNT = AccountTarget(30, "system", "active", None, None)


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


# Only an administrator reads the audit log
@pytest.mark.parametrize("actor", [DEVELOPER, BOT])
def test_only_an_admin_views_the_audit_log(actor):
	assert can(ADMIN, VIEW_AUDIT) is True
	assert can(actor, VIEW_AUDIT) is False


# A suspended administrator cannot read the audit log
def test_a_suspended_admin_cannot_view_the_audit_log():
	assert can(SUSPENDED_ADMIN, VIEW_AUDIT) is False


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


# A refused request leaves an event with the actor, the account and the permission
def test_require_records_the_refusal_in_the_audit_log(monkeypatch):
	calls = []
	monkeypatch.setattr(audit, "record_alone", lambda *args, **kwargs: calls.append((args, kwargs)))
	with Flask("test").app_context(), pytest.raises(Forbidden):
		require(DEVELOPER, APPROVE_REGISTRATION, COMPLETE)
	assert calls == [
		(("authz_fail", "failure", DEVELOPER.id, COMPLETE.id), {"details": {"permission": APPROVE_REGISTRATION}})
	]


# A refusal of an action that acts on no account has no target
def test_require_records_no_target_for_a_platform_action(monkeypatch):
	calls = []
	monkeypatch.setattr(audit, "record_alone", lambda *args, **kwargs: calls.append(args))
	with Flask("test").app_context(), pytest.raises(Forbidden):
		require(DEVELOPER, LIST_ACCOUNTS)
	assert calls == [("authz_fail", "failure", DEVELOPER.id, None)]


# A permitted request goes through without an error
def test_require_lets_a_permitted_request_through():
	with Flask("test").app_context():
		assert require(ADMIN, APPROVE_REGISTRATION, COMPLETE) is None


# The platform marker is the default resource of the actions that act on no account
def test_the_platform_marker_is_the_default_resource():
	assert can(ADMIN, LIST_ACCOUNTS, PLATFORM) is True


# Only a developer publishes an agent and lists the own ones
@pytest.mark.parametrize("action", [PUBLISH_AGENT, LIST_OWN_AGENTS])
@pytest.mark.parametrize("actor", [ADMIN, COMPANY, BOT, SUSPENDED_DEVELOPER])
def test_only_an_active_developer_publishes_and_lists_own_agents(action, actor):
	assert can(DEVELOPER, action) is True
	assert can(actor, action) is False


# The catalog is open to people and closed to the robot
@pytest.mark.parametrize("actor", [DEVELOPER, COMPANY, ADMIN])
def test_a_person_views_the_catalog(actor):
	assert can(actor, VIEW_CATALOG) is True


# The robot and a suspended account cannot read the catalog
@pytest.mark.parametrize("actor", [BOT, SUSPENDED_DEVELOPER, SUSPENDED_ADMIN])
def test_the_robot_and_a_suspended_account_cannot_view_the_catalog(actor):
	assert can(actor, VIEW_CATALOG) is False


# Only an active administrator reviews the agents
@pytest.mark.parametrize("actor", [DEVELOPER, COMPANY, BOT, SUSPENDED_ADMIN])
def test_only_an_active_admin_reviews_agents(actor):
	assert can(ADMIN, REVIEW_AGENTS) is True
	assert can(actor, REVIEW_AGENTS) is False


# Nobody suspends the platform account, not even an administrator
@pytest.mark.parametrize("actor", [ADMIN, DEVELOPER, BOT])
def test_nobody_changes_the_status_of_the_platform_account(actor):
	assert can(actor, MANAGE_ACCOUNT_STATUS, SYSTEM_ACCOUNT) is False


# Only an active developer or company runs agents and lists the own executions
@pytest.mark.parametrize("action", [EXECUTE_AGENT, LIST_OWN_EXECUTIONS])
@pytest.mark.parametrize("actor", [DEVELOPER, COMPANY])
def test_a_developer_and_a_company_run_agents(action, actor):
	assert can(actor, action) is True


# An administrator, the robot and a suspended account do not run agents
@pytest.mark.parametrize("action", [EXECUTE_AGENT, LIST_OWN_EXECUTIONS])
@pytest.mark.parametrize("actor", [ADMIN, BOT, SUSPENDED_DEVELOPER])
def test_other_roles_and_suspended_accounts_do_not_run_agents(action, actor):
	assert can(actor, action) is False


# Only an active developer reads the earnings of the agents
@pytest.mark.parametrize("actor", [COMPANY, ADMIN, BOT, SUSPENDED_DEVELOPER])
def test_only_an_active_developer_views_the_earnings(actor):
	assert can(DEVELOPER, VIEW_AGENT_EARNINGS) is True
	assert can(actor, VIEW_AGENT_EARNINGS) is False


# Only an active administrator reads the amounts of all the executions
@pytest.mark.parametrize("actor", [DEVELOPER, COMPANY, BOT, SUSPENDED_ADMIN])
def test_only_an_active_admin_views_all_the_executions(actor):
	assert can(ADMIN, VIEW_EXECUTIONS) is True
	assert can(actor, VIEW_EXECUTIONS) is False


# Only an active administrator unlocks an account
@pytest.mark.parametrize("actor", [DEVELOPER, COMPANY, BOT, SUSPENDED_ADMIN])
def test_only_an_active_admin_unlocks_an_account(actor):
	assert can(ADMIN, UNLOCK_ACCOUNT, DEVELOPER_ACCOUNT) is True
	assert can(actor, UNLOCK_ACCOUNT, DEVELOPER_ACCOUNT) is False

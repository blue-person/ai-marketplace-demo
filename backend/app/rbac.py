# Import libraries
from dataclasses import dataclass
from cadurso import Cadurso
from flask import abort

# Import modules
from . import audit
from .registration import is_profile_complete

# Constants
LIST_ACCOUNTS = "list_accounts"
MANAGE_ACCOUNT_STATUS = "manage_account_status"
LIST_REGISTRATIONS = "list_registrations"
APPROVE_REGISTRATION = "approve_registration"
REJECT_REGISTRATION = "reject_registration"
VIEW_ACCOUNT = "view_account"
RENAME_ACCOUNT = "rename_account"
MANAGE_API_KEY = "manage_api_key"
SIGN_IN = "sign_in"
SEND_CREDIT = "send_credit"
RECEIVE_CREDIT = "receive_credit"
VIEW_AUDIT = "view_audit"
PUBLISH_AGENT = "publish_agent"
LIST_OWN_AGENTS = "list_own_agents"
VIEW_CATALOG = "view_catalog"
REVIEW_AGENTS = "review_agents"
EXECUTE_AGENT = "execute_agent"
LIST_OWN_EXECUTIONS = "list_own_executions"
VIEW_AGENT_EARNINGS = "view_agent_earnings"
VIEW_EXECUTIONS = "view_executions"
UNLOCK_ACCOUNT = "unlock_account"


# Account that asks to perform an action
@dataclass(frozen=True)
class Actor:
	id: int
	role: str
	status: str


# Account on which an action is performed
@dataclass(frozen=True)
class AccountTarget:
	id: int
	role: str
	status: str
	organization: str | None
	country: str | None


# Resource of the actions that do not act on one account
@dataclass(frozen=True)
class Platform:
	pass


PLATFORM = Platform()

# Rule storage that is frozen at the end of this file
rules = Cadurso()


# True when the actor is a person that owns the account because the robot owns nothing
def _is_person_owner(actor: Actor, target: AccountTarget) -> bool:
	return actor.id == target.id and actor.role != "bot"


# Only administrators can browse the accounts
@rules.add_rule(LIST_ACCOUNTS)
def admin_lists_accounts(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "admin"


# Administrators suspend and reactivate any account except their own and the system account
@rules.add_rule(MANAGE_ACCOUNT_STATUS)
def admin_manages_account_status(actor: Actor, target: AccountTarget) -> bool:
	return actor.role == "admin" and actor.id != target.id and target.role != "system"


# Administrators and the approval robot can read the pending registrations
@rules.add_rule(LIST_REGISTRATIONS)
def staff_lists_registrations(actor: Actor, _platform: Platform) -> bool:
	return actor.role in ("admin", "bot")


# Administrators approve any account and the decision is left to them
@rules.add_rule(APPROVE_REGISTRATION)
def admin_approves_registration(actor: Actor, _target: AccountTarget) -> bool:
	return actor.role == "admin"


# The robot approves only the accounts with a complete profile
@rules.add_rule(APPROVE_REGISTRATION)
def bot_approves_complete_profile(actor: Actor, target: AccountTarget) -> bool:
	profile = {"organization": target.organization, "country": target.country}
	return actor.role == "bot" and is_profile_complete(profile)


# Only administrators reject registrations
@rules.add_rule(REJECT_REGISTRATION)
def admin_rejects_registration(actor: Actor, _target: AccountTarget) -> bool:
	return actor.role == "admin"


# Owners and administrators can read an account
@rules.add_rule(VIEW_ACCOUNT)
def owner_views_account(actor: Actor, target: AccountTarget) -> bool:
	return _is_person_owner(actor, target)


# Administrators can read any account
@rules.add_rule(VIEW_ACCOUNT)
def admin_views_account(actor: Actor, _target: AccountTarget) -> bool:
	return actor.role == "admin"


# Only the owner changes the name of an account
@rules.add_rule(RENAME_ACCOUNT)
def owner_renames_account(actor: Actor, target: AccountTarget) -> bool:
	return _is_person_owner(actor, target)


# Only the owner manages the key and the key of the robot comes from the environment
@rules.add_rule(MANAGE_API_KEY)
def owner_manages_api_key(actor: Actor, target: AccountTarget) -> bool:
	return _is_person_owner(actor, target)


# Every role can sign in except the robot
@rules.add_rule(SIGN_IN)
def person_signs_in(actor: Actor, _platform: Platform) -> bool:
	return actor.role in ("developer", "company", "admin")


# Developers and companies can send credit
@rules.add_rule(SEND_CREDIT)
def customer_sends_credit(actor: Actor, _platform: Platform) -> bool:
	return actor.role in ("developer", "company")


# Only developers and companies can receive credit
@rules.add_rule(RECEIVE_CREDIT)
def customer_receives_credit(_actor: Actor, target: AccountTarget) -> bool:
	return target.role in ("developer", "company")


# Only administrators can read the audit log
@rules.add_rule(VIEW_AUDIT)
def admin_views_audit(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "admin"


# Only developers publish agents
@rules.add_rule(PUBLISH_AGENT)
def developer_publishes_agent(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "developer"


# Only developers have agents of their own to list
@rules.add_rule(LIST_OWN_AGENTS)
def developer_lists_own_agents(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "developer"


# People read the catalog and the robot does not
@rules.add_rule(VIEW_CATALOG)
def person_views_catalog(actor: Actor, _platform: Platform) -> bool:
	return actor.role in ("developer", "company", "admin")


# Only administrators list the pending agents and approve or reject them
@rules.add_rule(REVIEW_AGENTS)
def admin_reviews_agents(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "admin"


# Developers and companies run agents and the other roles do not have credit to spend
@rules.add_rule(EXECUTE_AGENT)
def customer_executes_agent(actor: Actor, _platform: Platform) -> bool:
	return actor.role in ("developer", "company")


# Developers and companies read their own executions
@rules.add_rule(LIST_OWN_EXECUTIONS)
def customer_lists_own_executions(actor: Actor, _platform: Platform) -> bool:
	return actor.role in ("developer", "company")


# Only developers read what their agents earned
@rules.add_rule(VIEW_AGENT_EARNINGS)
def developer_views_agent_earnings(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "developer"


# Only administrators read the amounts of all the executions
@rules.add_rule(VIEW_EXECUTIONS)
def admin_views_executions(actor: Actor, _platform: Platform) -> bool:
	return actor.role == "admin"


# Only administrators unlock an account that failed too many logins
@rules.add_rule(UNLOCK_ACCOUNT)
def admin_unlocks_account(actor: Actor, _target: AccountTarget) -> bool:
	return actor.role == "admin"


# No rule can be added after this point and queries are accepted only from here
rules.freeze()


# Answer whether the actor may perform the action and an account that is not active never may
def can(actor: Actor, action: str, resource=PLATFORM) -> bool:
	if actor.status != "active":
		return False
	return bool(rules.is_allowed(actor, action, resource))


# Return the id of the account that the action acts on or None
def _target_id(resource) -> int | None:
	return resource.id if isinstance(resource, AccountTarget) else None


# Refuse the request with a 403 and record the refusal when the actor may not perform the action
def require(actor: Actor, action: str, resource=PLATFORM) -> None:
	if not can(actor, action, resource):
		audit.record_alone("authz_fail", "failure", actor.id, _target_id(resource), details={"permission": action})
		abort(403)

# Import libraries
from functools import wraps
from flask import abort, g, request, session

# Import modules
from . import audit
from .api_keys import hash_api_key
from .db import query
from .rbac import LIST_ACCOUNTS, AccountTarget, Actor, require

# Constants
TARGET_COLUMNS = "id, role, status, organization, country"


# Read the signed in account from the database so a change of role or status applies at once
def _read_signed_in_user() -> dict | None:
	account_id = session.get("account_id")
	if account_id is None:
		return None
	user = query("SELECT id, name, email, role, status FROM accounts WHERE id = %s", (account_id,), one=True)

	# A deleted account or one that is not active loses its session
	if user is None or user["status"] != "active":
		return None
	return user


# Return the signed in user or None and read it only once for each request
def current_user() -> dict | None:
	if "user" not in g:
		g.user = _read_signed_in_user()
	return g.user


# Return the signed in user as the actor of a permission check
def current_actor() -> Actor:
	user = current_user()
	return Actor(user["id"], user["role"], user["status"])


# Reject requests that have no signed in user
def login_required(view):

	# Check the session before calling the view
	@wraps(view)
	def wrapper(*args, **kwargs):
		if current_user() is None:
			abort(401)
		return view(*args, **kwargs)

	return wrapper


# Return the key sent as a bearer token in the Authorization header or None
def read_bearer_key(header: str) -> str | None:
	scheme, _, key = header.partition(" ")
	if scheme.lower() != "bearer" or not key.strip():
		return None
	return key.strip()


# Find the active account that owns the key by comparing the hashes
def _read_api_key_user() -> dict | None:
	key = read_bearer_key(request.headers.get("Authorization", ""))
	if key is None:
		return None
	user = query(
		"SELECT a.id, a.name, a.email, a.role, a.status FROM api_keys k "
		"JOIN accounts a ON a.id = k.account_id WHERE k.key_hash = %s",
		(hash_api_key(key),),
		one=True,
	)

	# A suspended account loses its key at once because the status is read on each request
	if user is None or user["status"] != "active":
		return None
	return user


# Return the account of the API key of the request as the actor of a permission check or None
def api_key_actor() -> Actor | None:
	if "api_user" not in g:
		g.api_user = _read_api_key_user()
	user = g.api_user
	return Actor(user["id"], user["role"], user["status"]) if user else None


# Reject requests that do not carry a valid API key
def api_key_required(view):

	# Check the key before calling the view
	@wraps(view)
	def wrapper(*args, **kwargs):
		if api_key_actor() is None:
			audit.record_alone("authn_api_key_fail", "failure", None)
			abort(401)
		return view(*args, **kwargs)

	return wrapper


# Return the account with that id as the target of an action or None
def find_target(account_id: int) -> AccountTarget | None:
	row = query(f"SELECT {TARGET_COLUMNS} FROM accounts WHERE id = %s", (account_id,), one=True)
	return AccountTarget(**row) if row else None


# Return the account with that email as the target of an action or None
def find_target_by_email(email: str) -> AccountTarget | None:
	row = query(f"SELECT {TARGET_COLUMNS} FROM accounts WHERE email = %s", (email,), one=True)
	return AccountTarget(**row) if row else None


# Load the account of the request and refuse the actor that may not perform the action on it
def authorized_target(actor: Actor, action: str, account_id: int) -> AccountTarget:
	target = find_target(account_id)

	# An actor that cannot browse accounts gets a 403 so it cannot probe which ids exist
	if target is None:
		require(actor, LIST_ACCOUNTS)
		abort(404, description="The account was not found.")
	require(actor, action, target)
	return target

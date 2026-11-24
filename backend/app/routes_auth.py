# Import libraries
from flask import Blueprint, abort, current_app, jsonify, request, session

# Import modules
from . import mail
from .countries import is_valid_country
from .db import DuplicateError, query, retry_on_deadlock, transaction
from .email_address import InvalidEmailError, normalize_email
from .passwords import MIN_PASSWORD_LENGTH, hash_password, needs_rehash, verify_password
from .rbac import SIGN_IN, Actor, can
from .registration import MAX_NAME_LENGTH, find_referrer_id, is_valid_organization
from .security import current_user, login_required

# Blueprint of the auth routes
bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Constants
LOGIN_ERROR = "Incorrect email or password."


# Insert the account in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _create_account(values: tuple) -> int:
	with transaction() as tx:
		return tx.insert(
			"INSERT INTO accounts (name, email, password_hash, role, status, organization, country, referred_by) "
			"VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
			values,
		)


# Replace the stored hash in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _replace_hash(account_id: int, password_hash: str) -> None:
	with transaction() as tx:
		tx.execute("UPDATE accounts SET password_hash = %s WHERE id = %s", (password_hash, account_id))


# Read the JSON body or fall back to the form fields
def _data() -> dict:
	return request.get_json(silent=True) or request.form.to_dict()


# Read the optional profile fields and refuse the ones that are not valid
def _read_profile(data: dict) -> tuple:
	organization = str(data.get("organization", "")).strip()
	country = str(data.get("country", "")).strip()
	if organization and not is_valid_organization(organization):
		abort(400, description="The organization must have between 2 and 100 characters.")
	if country and not is_valid_country(country):
		abort(400, description="The country is not valid.")

	# An empty field is stored as NULL so the profile counts as incomplete
	return organization or None, country or None


# Return the id of the referrer or None when no code was sent
def _read_referrer_id(data: dict) -> int | None:
	code = str(data.get("referral_code", "")).strip()
	if not code:
		return None
	referrer_id = find_referrer_id(code)
	if referrer_id is None:
		abort(400, description="The referral code is not valid.")
	return referrer_id


# True when the account is active and its role may sign in
def _may_sign_in(account: dict) -> bool:
	return can(Actor(account["id"], account["role"], account["status"]), SIGN_IN)


# Create an account and send a registration email
@bp.post("/register")
def register():
	data = _data()
	name = str(data.get("name", "")).strip()
	password = str(data.get("password", ""))
	role = str(data.get("role", ""))
	roles = current_app.config["CASE"]["roles"]

	# Only the roles that the case opens to the public can be requested
	if not roles.get(role, {}).get("public_registration"):
		abort(400, description="The account type is not valid.")
	if not name or len(name) > MAX_NAME_LENGTH:
		abort(400, description=f"The name must have between 1 and {MAX_NAME_LENGTH} characters.")
	try:
		email = normalize_email(str(data.get("email", "")))
	except InvalidEmailError as error:
		abort(400, description=str(error))
	if len(password) < MIN_PASSWORD_LENGTH:
		abort(400, description=f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")
	organization, country = _read_profile(data)
	referrer_id = _read_referrer_id(data)

	# The account needs approval only when its role requires it in case.json
	status = "pending" if roles[role]["requires_approval"] else "active"

	# The unique key on the email decides which of two simultaneous sign ups wins
	try:
		_create_account((name, email, hash_password(password), role, status, organization, country, referrer_id))
	except DuplicateError:
		return jsonify(error="The email is already registered."), 409

	# Pick the message that matches the approval status
	text = (
		"Your account was created and is pending approval."
		if status == "pending"
		else "Your account was created and you can now sign in."
	)

	# The account is kept even when the email cannot be sent
	mail.send(email, "Registration received", f"Hello {name}. {text}")
	return jsonify(message=text), 201


# Check the credentials and start a session
@bp.post("/login")
def login():
	data = _data()
	email = str(data.get("email", "")).strip().lower()
	password = str(data.get("password", ""))

	# Search the account by email
	account = query(
		"SELECT id, name, email, role, status, password_hash FROM accounts WHERE email = %s",
		(email,),
		one=True,
	)

	# Check the password even when the account does not exist
	stored_hash = account["password_hash"] if account else None
	password_matches = verify_password(stored_hash, password)

	# Every failed login gets the same answer
	if not account or not password_matches or not _may_sign_in(account):
		return jsonify(error=LOGIN_ERROR), 401

	# Replace the stored hash when it was made with older settings
	if needs_rehash(stored_hash):
		_replace_hash(account["id"], hash_password(password))

	# Store only the id because the role and the status are read again on each request
	session.permanent = True
	session["account_id"] = account["id"]

	# Send only the fields the interface needs
	return jsonify(
		user={"id": account["id"], "name": account["name"], "email": account["email"], "role": account["role"]}
	)


# End the session of the current user
@bp.route("/logout", methods=["GET", "POST"])
def logout():
	session.clear()
	return jsonify(message="Signed out.")


# Return the account of the signed in user
@bp.get("/me")
@login_required
def me():
	return jsonify(user=current_user())

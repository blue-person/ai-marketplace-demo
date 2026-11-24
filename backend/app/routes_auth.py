# Import libraries
from flask import Blueprint, abort, current_app, jsonify, request, session

# Import modules
from . import mail
from .db import DuplicateError, query, retry_on_deadlock, transaction
from .passwords import MIN_PASSWORD_LENGTH, hash_password, needs_rehash, verify_password
from .security import current_user, login_required

# Blueprint of the auth routes
bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Constants
LOGIN_ERROR = "Incorrect email or password."


# Insert the account in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _create_account(name: str, email: str, password_hash: str, role: str, status: str) -> int:
	with transaction() as tx:
		return tx.insert(
			"INSERT INTO accounts (name, email, password_hash, role, status) VALUES (%s, %s, %s, %s, %s)",
			(name, email, password_hash, role, status),
		)


# Replace the stored hash in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _replace_hash(account_id: int, password_hash: str) -> None:
	with transaction() as tx:
		tx.execute("UPDATE accounts SET password_hash = %s WHERE id = %s", (password_hash, account_id))


# Read the JSON body or fall back to the form fields
def _data() -> dict:
	return request.get_json(silent=True) or request.form.to_dict()


# Create an account and send a registration email
@bp.post("/register")
def register():
	data = _data()
	name = str(data.get("name", "")).strip()
	email = str(data.get("email", "")).strip().lower()
	password = str(data.get("password", ""))
	role = data.get("role", "")

	if not name or not email or "@" not in email:
		abort(400, description="Name and email are required.")
	if len(password) < MIN_PASSWORD_LENGTH:
		abort(400, description=f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")

	roles = current_app.config["CASE"]["roles"]

	# The account needs approval only when its role requires it in case.json
	status = "pending" if roles.get(role, {}).get("requires_approval") else "active"

	# The unique key on the email decides which of two simultaneous sign ups wins
	try:
		_create_account(name, email, hash_password(password), role, status)
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
	if not account or not password_matches or account["status"] != "active":
		return jsonify(error=LOGIN_ERROR), 401

	# Replace the stored hash when it was made with older settings
	if needs_rehash(stored_hash):
		_replace_hash(account["id"], hash_password(password))

	# Store the signed in user in the session cookie
	session.permanent = True
	session["account_id"] = account["id"]
	session["name"] = account["name"]
	session["email"] = account["email"]
	session["role"] = account["role"]

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

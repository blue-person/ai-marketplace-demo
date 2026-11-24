"""Sign up, sign in and sign out."""

import hashlib

from flask import Blueprint, abort, current_app, jsonify, request, session

from . import mail
from .db import commit, execute, query
from .security import current_user, login_required

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def hash_password(password: str) -> str:
	return hashlib.md5(password.encode()).hexdigest()


def _data() -> dict:
	return request.get_json(silent=True) or request.form.to_dict()


@bp.post("/register")
def register():
	data = _data()
	name = str(data.get("name", "")).strip()
	email = str(data.get("email", "")).strip().lower()
	password = str(data.get("password", ""))
	role = data.get("role", "")

	if not name or not email or "@" not in email:
		abort(400, description="Name and email are required.")
	if len(password) < 6:
		abort(400, description="The password must be at least 6 characters long.")

	if query("SELECT id FROM accounts WHERE email = %s", (email,), one=True):
		return jsonify(error="The email is already registered."), 409

	roles = current_app.config["CASE"]["roles"]
	status = "pending" if roles.get(role, {}).get("requires_approval") else "active"
	execute(
		"INSERT INTO accounts (name, email, password_hash, role, status) VALUES (%s, %s, %s, %s, %s)",
		(name, email, hash_password(password), role, status),
	)
	commit()

	text = (
		"Your account was created and is pending approval."
		if status == "pending"
		else "Your account was created and you can now sign in."
	)
	mail.send(email, "Registration received", f"Hello {name}. {text}")
	return jsonify(message=text), 201


@bp.post("/login")
def login():
	data = _data()
	email = str(data.get("email", "")).strip().lower()
	password = str(data.get("password", ""))

	# The email and the hash travel as parameters, so they are never read as part of the SQL text.
	account = query(
		"SELECT * FROM accounts WHERE email = %s AND password_hash = %s",
		(email, hash_password(password)),
		one=True,
	)
	if not account:
		return jsonify(error="Incorrect email or password."), 401
	if account["status"] != "active":
		return jsonify(error=f"The account status is '{account['status']}'."), 403

	session.permanent = True
	session["account_id"] = account["id"]
	session["name"] = account["name"]
	session["email"] = account["email"]
	session["role"] = account["role"]
	return jsonify(user=account)


@bp.route("/logout", methods=["GET", "POST"])
def logout():
	session.clear()
	return jsonify(message="Signed out.")


@bp.get("/me")
@login_required
def me():
	return jsonify(user=current_user())

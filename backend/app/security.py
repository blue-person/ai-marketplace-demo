# Import libraries
from functools import wraps
from flask import abort, session


def current_user():
	if "account_id" not in session:
		return None
	return {
		"id": session["account_id"],
		"name": session.get("name"),
		"email": session.get("email"),
		"role": session.get("role"),
	}


def login_required(view):
	@wraps(view)
	def wrapper(*args, **kwargs):
		if current_user() is None:
			abort(401)
		return view(*args, **kwargs)

	return wrapper


# Use it below the route decorator as in @role_required("admin")
def role_required(*roles):
	def decorator(view):
		@wraps(view)
		def wrapper(*args, **kwargs):
			user = current_user()
			if user is None:
				abort(401)
			if user["role"] not in roles:
				abort(403)
			return view(*args, **kwargs)

		return wrapper

	return decorator

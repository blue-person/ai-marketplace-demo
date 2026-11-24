# Import libraries
from functools import wraps
from flask import abort, session


# Return the logged in user from the session or None
def current_user():
	if "account_id" not in session:
		return None
	return {
		"id": session["account_id"],
		"name": session.get("name"),
		"email": session.get("email"),
		"role": session.get("role"),
	}


# Reject requests that have no logged in user
def login_required(view):

	# Check the session before calling the view
	@wraps(view)
	def wrapper(*args, **kwargs):
		if current_user() is None:
			abort(401)
		return view(*args, **kwargs)

	return wrapper


# Use it below the route decorator and list the allowed roles
def role_required(*roles):

	# Receive the view to protect
	def decorator(view):

		# Check the session and the role before calling the view
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

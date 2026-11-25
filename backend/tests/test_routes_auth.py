# Import libraries
import pytest
from flask import Flask

# Import modules
from app import routes_auth as auth
from app.login_throttle import Reservation
from app.routes_auth import _data, bp


# A JSON object is read as it comes
def test_a_json_object_is_read_as_it_comes():
	with Flask("test").test_request_context(json={"email": "a@b.test"}):
		assert _data() == {"email": "a@b.test"}


# Form fields are read when the body is not JSON
def test_form_fields_are_read_when_the_body_is_not_json():
	with Flask("test").test_request_context(data={"email": "a@b.test"}):
		assert _data() == {"email": "a@b.test"}


# A JSON body that is not an object gives no data and does not break the route
@pytest.mark.parametrize("body", [[1, 2], "text", 5, True])
def test_a_json_body_that_is_not_an_object_gives_no_data(body):
	with Flask("test").test_request_context(json=body):
		assert _data() == {}


# App with only the auth routes and no database, enough for the routes that do not read it
def _client():
	app = Flask("test")
	app.secret_key = "test"
	app.register_blueprint(bp)
	return app.test_client()


# A link or an image on another page cannot sign the user out with a GET
def test_logout_refuses_a_get_request():
	assert _client().get("/api/auth/logout").status_code == 405


# The interface signs out with a POST
def test_logout_accepts_a_post_request():
	assert _client().post("/api/auth/logout").status_code == 200


# Constants
STORED_EMAIL = "dev1@marketplace.test"
ACCOUNT = {
	"id": 5,
	"name": "Dev",
	"email": STORED_EMAIL,
	"role": "developer",
	"status": "active",
	"password_hash": "stored-hash",
}


# Replace the database, the hash and the counter and return the list of calls and the client
def _login_client(monkeypatch, account=ACCOUNT, seconds_left=None, password_ok=True, lock=None):
	lock = lock or {}
	calls = []
	monkeypatch.setattr(auth, "query", lambda sql, params=(), one=False: account)
	monkeypatch.setattr(
		auth.login_throttle,
		"reserve_attempt",
		lambda email: calls.append(("reserve", email, None)) or Reservation(seconds_left=seconds_left, **lock),
	)
	monkeypatch.setattr(auth.login_throttle, "clear", lambda email: calls.append(("clear", email)))
	monkeypatch.setattr(
		auth, "verify_password", lambda stored, password: calls.append(("verify", stored)) or password_ok
	)
	monkeypatch.setattr(auth, "needs_rehash", lambda stored: False)
	monkeypatch.setattr(auth.sessions, "start", lambda account_id: calls.append(("start", account_id)) or "tok")
	monkeypatch.setattr(auth.audit, "record_alone", lambda *args, **kwargs: calls.append(("audit", args[0])))
	return calls, _client()


# Body of a login request
def _credentials(email=STORED_EMAIL, password="x"):
	return {"email": email, "password": password}


# A locked email gets a 429 with the minutes and the header and the password is not checked
def test_a_locked_email_gets_a_429_and_the_password_is_not_checked(monkeypatch):
	calls, client = _login_client(monkeypatch, seconds_left=1500)
	response = client.post("/api/auth/login", json=_credentials())
	assert response.status_code == 429
	assert response.headers["Retry-After"] == "1500"
	assert response.get_json() == {"error": "The account is locked. Try again in 25 minutes."}
	assert [name for name, *_ in calls] == ["reserve"]


# The minutes are rounded up and one minute is singular
@pytest.mark.parametrize(
	"seconds, text", [(1, "1 minute."), (60, "1 minute."), (61, "2 minutes."), (7200, "120 minutes.")]
)
def test_the_minutes_are_rounded_up(monkeypatch, seconds, text):
	_, client = _login_client(monkeypatch, seconds_left=seconds)
	assert client.post("/api/auth/login", json=_credentials()).get_json()["error"].endswith(text)


# A locked email that does not exist gets the same answer as one that does
def test_an_email_without_account_gets_the_same_lock_answer(monkeypatch):
	_, client = _login_client(monkeypatch, account=None, seconds_left=900)
	response = client.post("/api/auth/login", json=_credentials("nobody@x.test"))
	assert response.status_code == 429
	assert response.get_json() == {"error": "The account is locked. Try again in 15 minutes."}


# The attempt is counted before the password is checked
def test_the_attempt_is_counted_before_the_password_is_checked(monkeypatch):
	calls, client = _login_client(monkeypatch)
	client.post("/api/auth/login", json=_credentials())
	names = [name for name, *_ in calls]
	assert names.index("reserve") < names.index("verify")


# The counter uses the email stored in the account and not the spelling that was typed
def test_the_counter_uses_the_stored_email(monkeypatch):
	calls, client = _login_client(monkeypatch)
	client.post("/api/auth/login", json=_credentials("dév1@marketplace.test"))
	assert calls[0] == ("reserve", STORED_EMAIL, None)
	assert ("clear", STORED_EMAIL) in calls


# An email without account is counted with the typed text and without an account id
def test_an_email_without_account_is_counted_with_the_typed_text(monkeypatch):
	calls, client = _login_client(monkeypatch, account=None)
	client.post("/api/auth/login", json=_credentials("Nobody@x.test"))
	assert calls[0] == ("reserve", "nobody@x.test", None)


# A wrong password gets the generic 401 and the counter is not cleared
def test_a_wrong_password_gets_the_generic_answer_and_keeps_the_count(monkeypatch):
	calls, client = _login_client(monkeypatch, password_ok=False)
	response = client.post("/api/auth/login", json=_credentials())
	assert response.status_code == 401
	assert response.get_json() == {"error": "Incorrect email or password."}
	assert "clear" not in [name for name, *_ in calls]
	assert "start" not in [name for name, *_ in calls]


# A good password clears the counter and starts a session of the server with its token in the cookie
def test_a_good_login_clears_the_counter_and_starts_a_server_session(monkeypatch):
	calls, client = _login_client(monkeypatch)
	response = client.post("/api/auth/login", json=_credentials())
	assert response.status_code == 200
	assert ("clear", STORED_EMAIL) in calls
	assert ("start", 5) in calls
	with client.session_transaction() as stored:
		assert stored["sid"] == "tok"
		assert "account_id" not in stored


# A good password of an account that cannot sign in keeps the count and starts nothing
def test_a_good_password_of_a_pending_account_keeps_the_count(monkeypatch):
	calls, client = _login_client(monkeypatch, account={**ACCOUNT, "status": "pending"})
	assert client.post("/api/auth/login", json=_credentials()).status_code == 401
	assert "clear" not in [name for name, *_ in calls]
	assert "start" not in [name for name, *_ in calls]


# A password that is too long counts as a failed attempt and is not hashed
def test_a_password_that_is_too_long_counts_as_a_failure(monkeypatch):
	calls, client = _login_client(monkeypatch)
	assert client.post("/api/auth/login", json=_credentials(password="x" * 65)).status_code == 401
	assert [name for name, *_ in calls][:1] == ["reserve"]
	assert "verify" not in [name for name, *_ in calls]


# An email longer than the column gets no row in the counter
def test_an_email_that_is_too_long_gets_no_row_in_the_counter(monkeypatch):
	calls, client = _login_client(monkeypatch)
	assert client.post("/api/auth/login", json=_credentials("a" * 255)).status_code == 401
	assert "reserve" not in [name for name, *_ in calls]


# The logout closes the session in the server
def test_the_logout_closes_the_session_in_the_server(monkeypatch):
	ended = []
	monkeypatch.setattr(auth, "current_user", lambda: {"id": 5})
	monkeypatch.setattr(auth.audit, "record_alone", lambda *args, **kwargs: None)
	monkeypatch.setattr(auth.sessions, "end", ended.append)
	client = _client()
	with client.session_transaction() as stored:
		stored["sid"] = "tok"
	assert client.post("/api/auth/logout").status_code == 200
	assert ended == ["tok"]


# A failed attempt that closed the lock writes the event of the lock after the failure
def test_a_failed_tenth_attempt_writes_the_event_of_the_lock(monkeypatch):
	calls, client = _login_client(monkeypatch, password_ok=False, lock={"closed_level": 1, "closed_seconds": 1800})
	assert client.post("/api/auth/login", json=_credentials()).status_code == 401
	events = [name for kind, name in (c for c in calls if c[0] == "audit")]
	assert events == ["authn_login_fail", "authn_account_locked"]


# A good tenth attempt removes the lock so no event of a lock is written
def test_a_good_tenth_attempt_writes_no_event_of_a_lock(monkeypatch):
	calls, client = _login_client(monkeypatch, lock={"closed_level": 1, "closed_seconds": 1800})
	assert client.post("/api/auth/login", json=_credentials()).status_code == 200
	assert "authn_account_locked" not in [name for kind, name in (c for c in calls if c[0] == "audit")]

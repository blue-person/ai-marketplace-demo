# Import libraries
import pytest
from flask import Flask

# Import modules
from app import security
from app.rbac import Actor
from app.security import read_bearer_key, read_json_object


# A bearer header gives the key
def test_reads_the_key_of_a_bearer_header():
	assert read_bearer_key("Bearer mk_abc123") == "mk_abc123"


# The name of the scheme does not depend on the case
def test_reads_the_key_when_the_scheme_is_in_lowercase():
	assert read_bearer_key("bearer mk_abc123") == "mk_abc123"


# Without the header there is no key
def test_an_empty_header_gives_no_key():
	assert read_bearer_key("") is None


# Another scheme such as Basic is not a key
def test_another_scheme_gives_no_key():
	assert read_bearer_key("Basic bWs6YWJj") is None


# The scheme alone has no key
def test_the_scheme_without_a_key_gives_no_key():
	assert read_bearer_key("Bearer ") is None
	assert read_bearer_key("Bearer") is None


# A JSON object is returned as it comes
def test_a_json_object_is_returned_as_it_comes():
	with Flask("test").test_request_context(json={"amount": "5.00"}):
		assert read_json_object() == {"amount": "5.00"}


# A body that is not an object gives an empty dictionary so the route can answer 400
@pytest.mark.parametrize("body", [[1, 2], "text", 5, True])
def test_a_json_body_that_is_not_an_object_gives_an_empty_dictionary(body):
	with Flask("test").test_request_context(json=body):
		assert read_json_object() == {}


# Text that is not JSON gives an empty dictionary
def test_text_that_is_not_json_gives_an_empty_dictionary():
	with Flask("test").test_request_context(data="{bad", content_type="application/json"):
		assert read_json_object() == {}


# A request without a body gives an empty dictionary
def test_a_request_without_a_body_gives_an_empty_dictionary():
	with Flask("test").test_request_context():
		assert read_json_object() == {}


# Constants
KEY_ACTOR = Actor(1, "company", "active")
SESSION_USER = {"id": 2, "name": "Dev", "email": "d@x.test", "role": "developer", "status": "active"}
JSON_HEADERS = {"X-Requested-With": "fetch", "Content-Type": "application/json"}


# Small app with one route behind the decorator and the key and the session replaced by fakes
def _client(monkeypatch, key_actor=KEY_ACTOR, session_user=SESSION_USER):
	failures = []
	monkeypatch.setattr(security, "api_key_actor", lambda: key_actor)
	monkeypatch.setattr(security, "current_user", lambda: session_user)
	monkeypatch.setattr(security.audit, "record_alone", lambda *args, **kwargs: failures.append(args))
	app = Flask("test")

	@app.route("/run", methods=["GET", "POST"])
	@security.key_or_session_required
	def run():
		return {"actor_id": security.key_or_session_actor().id}

	return app.test_client(), failures


# A valid key works without the header and the JSON type that the session needs
def test_a_valid_key_needs_no_csrf_header(monkeypatch):
	client, _failures = _client(monkeypatch)
	response = client.post("/run", headers={"Authorization": "Bearer mk_abc"}, data="x")
	assert response.status_code == 200
	assert response.get_json() == {"actor_id": 1}


# A key that is not valid is refused and recorded even when a session exists
def test_an_invalid_key_is_refused_and_recorded_even_with_a_session(monkeypatch):
	client, failures = _client(monkeypatch, key_actor=None)
	response = client.post("/run", headers={"Authorization": "Bearer mk_bad", **JSON_HEADERS})
	assert response.status_code == 401
	assert failures == [("authn_api_key_fail", "failure", None)]


# A session that changes data without the header of the page is refused with a 403
def test_a_session_post_without_the_header_is_refused(monkeypatch):
	client, _failures = _client(monkeypatch)
	response = client.post("/run", headers={"Content-Type": "application/json"}, data="{}")
	assert response.status_code == 403


# A session that changes data with a form type is refused with a 415
@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"])
def test_a_session_post_with_a_simple_type_is_refused(monkeypatch, content_type):
	client, _failures = _client(monkeypatch)
	response = client.post("/run", headers={"X-Requested-With": "fetch", "Content-Type": content_type}, data="x")
	assert response.status_code == 415


# A session with the header and a JSON body is accepted
def test_a_session_post_with_the_header_and_json_is_accepted(monkeypatch):
	client, _failures = _client(monkeypatch)
	response = client.post("/run", headers=JSON_HEADERS, data="{}")
	assert response.status_code == 200
	assert response.get_json() == {"actor_id": 2}


# A session that only reads does not need the header
def test_a_session_get_needs_no_header(monkeypatch):
	client, _failures = _client(monkeypatch)
	assert client.get("/run").status_code == 200


# Without a key and without a session the request is refused with a 401
def test_a_request_without_key_and_session_is_refused(monkeypatch):
	client, _failures = _client(monkeypatch, session_user=None)
	assert client.get("/run").status_code == 401
	assert client.post("/run", headers=JSON_HEADERS, data="{}").status_code == 401

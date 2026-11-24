# Import libraries
import pytest
from flask import Flask

# Import modules
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

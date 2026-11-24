# Import libraries
import pytest
from flask import Flask

# Import modules
from app.routes_auth import _data


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

# Import libraries
import pytest
from flask import Flask

# Import modules
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

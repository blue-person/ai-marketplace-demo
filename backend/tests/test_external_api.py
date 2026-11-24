# Import libraries
import pytest
from flask import Flask

# Import modules
from app import external_api


# Answer that keeps the status and the JSON body of a response
class FakeResponse:
	def __init__(self, status_code=200, body=None, invalid_json=False):
		self.status_code = status_code
		self.ok = status_code < 400
		self._body = body
		self._invalid_json = invalid_json

	def json(self):
		if self._invalid_json:
			raise ValueError("not json")
		return self._body


# Answer the next request of the module with the given response
def _answer(monkeypatch, response):
	monkeypatch.setattr(external_api, "get", lambda address, params=None: response)
	monkeypatch.setattr(external_api, "url", lambda path: f"http://api.test/{path}")


# The identifiers are read from the data list
def test_list_models_returns_the_identifiers(monkeypatch):
	_answer(monkeypatch, FakeResponse(body={"data": [{"id": "a/one", "name": "One"}, {"id": "a/two"}]}))
	assert external_api.list_models() == ["a/one", "a/two"]


# An answer with an error status is a failure of the external API
def test_list_models_refuses_an_error_status(monkeypatch):
	_answer(monkeypatch, FakeResponse(status_code=503))
	with pytest.raises(external_api.ExternalApiError):
		external_api.list_models()


# A body that is not JSON or has another shape is a failure of the external API
@pytest.mark.parametrize("body", [{"models": []}, {"data": [{"name": "x"}]}, {"data": 5}, [1, 2], None])
def test_list_models_refuses_an_unexpected_shape(monkeypatch, body):
	_answer(monkeypatch, FakeResponse(body=body))
	with pytest.raises(external_api.ExternalApiError):
		external_api.list_models()


# A body that cannot be decoded is a failure of the external API
def test_list_models_refuses_a_body_that_is_not_json(monkeypatch):
	_answer(monkeypatch, FakeResponse(invalid_json=True))
	with pytest.raises(external_api.ExternalApiError):
		external_api.list_models()


# The address of the models list is built from the configured base
def test_list_models_asks_for_the_models_path(monkeypatch):
	asked = []
	monkeypatch.setattr(external_api, "url", lambda path: asked.append(path) or f"http://api.test/{path}")
	monkeypatch.setattr(external_api, "get", lambda address, params=None: FakeResponse(body={"data": []}))
	with Flask("test").app_context():
		external_api.list_models()
	assert asked == ["models"]

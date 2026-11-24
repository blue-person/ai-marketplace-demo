# Import libraries
import requests
from flask import current_app


# Raised when a request to the external API fails at the network level
class ExternalApiError(RuntimeError):
	pass


# Send the API key as a bearer token only when one is configured
def _headers() -> dict:
	headers = {"Accept": "application/json"}
	key = current_app.config["EXTERNAL_API_KEY"]
	if key:
		headers["Authorization"] = f"Bearer {key}"
	return headers


# Build the full external API address for a path
def url(path: str) -> str:
	return f"{current_app.config['EXTERNAL_API_BASE_URL']}/{path.lstrip('/')}"


# Send a GET request and turn network errors into ExternalApiError
def get(address: str, params: dict | None = None) -> requests.Response:
	try:
		return requests.get(address, params=params, headers=_headers(), timeout=15)
	except requests.RequestException as error:
		raise ExternalApiError(str(error)) from error


# Send a POST request with a JSON body and turn network errors into ExternalApiError
def post(address: str, body: dict) -> requests.Response:
	try:
		return requests.post(address, json=body, headers=_headers(), timeout=15)
	except requests.RequestException as error:
		raise ExternalApiError(str(error)) from error

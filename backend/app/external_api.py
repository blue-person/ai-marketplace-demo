"""HTTP client for the case's external API (simulated or real)."""
import requests
from flask import current_app


class ExternalApiError(RuntimeError):
    pass


def _headers() -> dict:
    headers = {"Accept": "application/json"}
    key = current_app.config["EXTERNAL_API_KEY"]
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def url(path: str) -> str:
    return f"{current_app.config['EXTERNAL_API_BASE_URL']}/{path.lstrip('/')}"


def get(address: str, params: dict | None = None) -> requests.Response:
    try:
        return requests.get(address, params=params, headers=_headers(), timeout=15)
    except requests.RequestException as error:
        raise ExternalApiError(str(error)) from error


def post(address: str, body: dict) -> requests.Response:
    try:
        return requests.post(address, json=body, headers=_headers(), timeout=15)
    except requests.RequestException as error:
        raise ExternalApiError(str(error)) from error

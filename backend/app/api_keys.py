# Import libraries
import hashlib
import secrets
from typing import NamedTuple

# Constants
KEY_PREFIX = "mk_"
KEY_BYTES = 32
DISPLAY_PREFIX_LENGTH = 8


# A new key with the values that are stored in the database
class NewApiKey(NamedTuple):
	key: str
	key_hash: str
	prefix: str


# Hash a key with SHA-256 so it can be searched in the database without storing it
def hash_api_key(key: str) -> str:
	return hashlib.sha256(key.encode("utf-8")).hexdigest()


# Describe a key that already exists with its hash and the prefix that identifies it
def describe_api_key(key: str) -> NewApiKey:
	return NewApiKey(key, hash_api_key(key), key[:DISPLAY_PREFIX_LENGTH])


# Create a random key and return it with its hash and the prefix that identifies it
def new_api_key() -> NewApiKey:
	return describe_api_key(KEY_PREFIX + secrets.token_urlsafe(KEY_BYTES))

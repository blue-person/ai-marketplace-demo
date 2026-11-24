# Import modules
from app.api_keys import hash_api_key, new_api_key


# The hash of the text abc is a known SHA-256 value
def test_hash_matches_the_known_sha256_value():
	assert hash_api_key("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


# The stored hash is the hash of the key that is shown to the user
def test_new_key_comes_with_its_own_hash():
	created = new_api_key()
	assert created.key_hash == hash_api_key(created.key)


# The key is never stored in the clear
def test_hash_is_not_the_key():
	created = new_api_key()
	assert created.key_hash != created.key


# The prefix is the beginning of the key and has a fixed length
def test_prefix_is_the_start_of_the_key():
	created = new_api_key()
	assert created.key.startswith(created.prefix)
	assert len(created.prefix) == 8


# Two keys are never the same
def test_two_keys_are_different():
	assert new_api_key().key != new_api_key().key

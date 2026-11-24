# Import libraries
from argon2 import PasswordHasher

# Import modules
from app.passwords import hash_password, needs_rehash, verify_password

# Constants
PASSWORD = "a-correct-horse-battery"


# The right password matches its own hash
def test_accepts_the_password_that_made_the_hash():
	assert verify_password(hash_password(PASSWORD), PASSWORD) is True


# Any other password does not match
def test_refuses_a_different_password():
	assert verify_password(hash_password(PASSWORD), "another-long-password") is False


# A missing account never matches even with the dummy hash check
def test_refuses_every_password_when_there_is_no_stored_hash():
	assert verify_password(None, PASSWORD) is False


# A damaged hash counts as a failed check and not as an error
def test_refuses_a_malformed_stored_hash():
	assert verify_password("not-a-hash", PASSWORD) is False


# The salt makes two hashes of one password different
def test_gives_different_hashes_to_the_same_password():
	assert hash_password(PASSWORD) != hash_password(PASSWORD)


# A hash made with the current settings does not need a replacement
def test_does_not_ask_to_rehash_a_current_hash():
	assert needs_rehash(hash_password(PASSWORD)) is False


# A hash made with weaker settings must be replaced
def test_asks_to_rehash_a_hash_made_with_weaker_settings():
	weak_hash = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
	assert needs_rehash(weak_hash) is True

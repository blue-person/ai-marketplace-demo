# Import libraries
import pytest
from argon2 import PasswordHasher

# Import modules
from app.passwords import MAX_PASSWORD_LENGTH, hash_password, is_acceptable_password, needs_rehash, verify_password

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


# A password with the right length and every kind of character is accepted
def test_accepts_a_password_that_meets_every_rule():
	assert is_acceptable_password("Correct-horse-battery-7") is True


# A password of 14 characters is too short and 15 is enough
def test_requires_at_least_fifteen_characters():
	assert is_acceptable_password("Abcdefghijkl-1") is False
	assert is_acceptable_password("Abcdefghijklm-1") is True


# A password of 64 characters fits and 65 does not
def test_accepts_at_most_sixty_four_characters():
	assert is_acceptable_password("A1-" + "x" * (MAX_PASSWORD_LENGTH - 3)) is True
	assert is_acceptable_password("A1-" + "x" * (MAX_PASSWORD_LENGTH - 2)) is False


# Each missing kind of character is refused
@pytest.mark.parametrize(
	"password",
	["correct-horse-battery-7", "CORRECT-HORSE-BATTERY-7", "Correct-horse-battery-x", "Correct horse battery 7"],
	ids=["no uppercase", "no lowercase", "no number", "only spaces and no symbol"],
)
def test_refuses_a_password_that_lacks_a_kind_of_character(password):
	assert is_acceptable_password(password) is False


# Accented letters and emoji follow the same rules as ASCII characters
def test_accepts_unicode_letters_and_symbols():
	assert is_acceptable_password("Contraseña-ñandú-9") is True
	assert is_acceptable_password("Contraseñalarga9🙂xx") is True

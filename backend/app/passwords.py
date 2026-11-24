# Import libraries
import secrets
import unicodedata
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Constants
MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 64
PASSWORD_RULES = (
	f"The password must have between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters, "
	"with an uppercase letter, a lowercase letter, a number and a symbol."
)
TIME_COST = 2
MEMORY_COST_KIB = 19 * 1024
PARALLELISM = 1

# Argon2 hasher with the cost settings
_hasher = PasswordHasher(time_cost=TIME_COST, memory_cost=MEMORY_COST_KIB, parallelism=PARALLELISM)

# Dummy hash that makes a missing account cost the same as a wrong password
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


# True for a punctuation mark or a symbol according to the Unicode categories
def _is_symbol(character: str) -> bool:
	return unicodedata.category(character)[0] in ("P", "S")


# True when the password has the length and the kinds of characters that the rules ask for
def is_acceptable_password(password: str) -> bool:
	if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
		return False
	has_uppercase = any(character.isupper() for character in password)
	has_lowercase = any(character.islower() for character in password)
	has_number = any(character.isdecimal() for character in password)
	has_symbol = any(_is_symbol(character) for character in password)
	return has_uppercase and has_lowercase and has_number and has_symbol


# The salt and the settings are stored inside the hash itself
def hash_password(password: str) -> str:
	return _hasher.hash(password)


# A wrong password or a missing or malformed hash counts as a failed check
def verify_password(stored_hash: str | None, password: str) -> bool:
	hash_to_check = _DUMMY_HASH if stored_hash is None else stored_hash
	try:
		matches = _hasher.verify(hash_to_check, password)
	except (VerificationError, InvalidHashError):
		return False

	# A missing account cannot match even though the dummy hash was checked
	return matches and stored_hash is not None


# True when the hash was made with older settings and should be replaced
def needs_rehash(stored_hash: str) -> bool:
	return _hasher.check_needs_rehash(stored_hash)

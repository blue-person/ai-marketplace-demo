# Import libraries
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Constants
MIN_PASSWORD_LENGTH = 15
TIME_COST = 2
MEMORY_COST_KIB = 19 * 1024
PARALLELISM = 1

_hasher = PasswordHasher(time_cost=TIME_COST, memory_cost=MEMORY_COST_KIB, parallelism=PARALLELISM)

# A real hash of a random value so a missing account takes a similar time as a wrong password
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


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
	return matches and stored_hash is not None


# True when the hash was made with older settings and should be replaced
def needs_rehash(stored_hash: str) -> bool:
	return _hasher.check_needs_rehash(stored_hash)

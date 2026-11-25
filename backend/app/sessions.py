# Import libraries
import hashlib
import secrets

# Import modules
from .db import retry_on_deadlock, transaction

# Constants
IDLE_TIMEOUT_SECONDS = 15 * 60
ABSOLUTE_TIMEOUT_SECONDS = 8 * 60 * 60
TOKEN_BYTES = 32


# Hash of the token so a copy of the table cannot be used to sign in
def _hash(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Create a session for the account and return the random token that the browser keeps
@retry_on_deadlock
def start(account_id: int) -> str:
	token = secrets.token_urlsafe(TOKEN_BYTES)
	with transaction() as tx:
		tx.insert("INSERT INTO sessions (id_hash, account_id) VALUES (%s, %s)", (_hash(token), account_id))
	return token


# Renew the session and return its account id, or None when it is idle, too old, closed or unknown
@retry_on_deadlock
def touch(token: str) -> int | None:
	token_hash = _hash(token)

	# The conditions and the renewal are one statement, so a session that expired cannot be renewed
	with transaction() as tx:
		changed = tx.execute(
			"UPDATE sessions SET last_seen_at = NOW(6) WHERE id_hash = %s AND revoked_at IS NULL "
			"AND last_seen_at > NOW(6) - INTERVAL %s SECOND AND created_at > NOW(6) - INTERVAL %s SECOND",
			(token_hash, IDLE_TIMEOUT_SECONDS, ABSOLUTE_TIMEOUT_SECONDS),
		)
		if not changed:
			return None
		return tx.query("SELECT account_id FROM sessions WHERE id_hash = %s", (token_hash,), one=True)["account_id"]


# Close the session in the server so a copy of its cookie stops working
@retry_on_deadlock
def end(token: str) -> None:
	with transaction() as tx:
		tx.execute("UPDATE sessions SET revoked_at = NOW(6) WHERE id_hash = %s AND revoked_at IS NULL", (_hash(token),))

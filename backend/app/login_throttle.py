# Import libraries
import hashlib
from typing import NamedTuple

# Import modules
from . import audit
from .db import query, retry_on_deadlock, transaction

# Constants
MAX_FAILURES = 10
BASE_LOCK_SECONDS = 30 * 60
MAX_LOCK_SECONDS = 24 * 60 * 60
WINDOW_SECONDS = 24 * 60 * 60
PURGE_AFTER_SECONDS = 7 * 24 * 60 * 60
PURGE_BATCH = 100


# Result of counting an attempt with the seconds left when the email is locked and the lock this attempt closed
class Reservation(NamedTuple):
	seconds_left: int | None = None
	closed_level: int | None = None
	closed_seconds: int | None = None


# Hash of the email so the table never stores what was typed in the login form
def _key(email: str) -> str:
	return hashlib.sha256(email.encode("utf-8")).hexdigest()


# Seconds that the lock of that level lasts, doubling with each level up to the maximum
def lock_seconds(level: int) -> int:
	return min(BASE_LOCK_SECONDS * 2 ** (level - 1), MAX_LOCK_SECONDS)


# Delete a batch of old rows whose lock already ended so the table does not grow with invented emails
def _purge_old_rows(tx) -> None:
	tx.execute(
		"DELETE FROM login_throttle WHERE updated_at < NOW() - INTERVAL %s SECOND "
		"AND (locked_until IS NULL OR locked_until < NOW()) LIMIT %s",
		(PURGE_AFTER_SECONDS, PURGE_BATCH),
	)


# Count the attempt before the password is checked and return the seconds left when the email is locked
@retry_on_deadlock
def reserve_attempt(email: str) -> Reservation:
	key = _key(email)

	# The row exists before it is locked so the first failure of an email has something to lock
	with transaction() as tx:
		created = tx.execute(
			"INSERT INTO login_throttle (email_hash) VALUES (%s) ON DUPLICATE KEY UPDATE email_hash = email_hash",
			(key,),
		)
		row = tx.query(
			"SELECT failures, lock_level, locked_until > NOW() AS locked, "
			"TIMESTAMPDIFF(SECOND, NOW(), locked_until) AS remaining, "
			"updated_at < NOW() - INTERVAL %s SECOND AS stale FROM login_throttle WHERE email_hash = %s FOR UPDATE",
			(WINDOW_SECONDS, key),
			one=True,
		)

		# A locked email does not count the attempt and the password is not checked
		if row["locked"]:
			return Reservation(seconds_left=max(row["remaining"], 1))
		failures = 1 if row["stale"] else row["failures"] + 1
		reservation = Reservation()
		if failures < MAX_FAILURES:
			tx.execute("UPDATE login_throttle SET failures = %s WHERE email_hash = %s", (failures, key))
		else:
			level = row["lock_level"] + 1
			seconds = lock_seconds(level)
			tx.execute(
				"UPDATE login_throttle SET failures = 0, lock_level = %s, locked_until = NOW() + INTERVAL %s SECOND "
				"WHERE email_hash = %s",
				(level, seconds, key),
			)
			reservation = Reservation(closed_level=level, closed_seconds=seconds)
		if created:
			_purge_old_rows(tx)
		return reservation


# Write the event of a lock only when the attempt that closed it failed, because a good one removes it
def record_lock(reservation: Reservation, email: str, account_id: int | None) -> None:
	if reservation.closed_level is None:
		return
	audit.record_alone(
		"authn_account_locked",
		"failure",
		None,
		account_id,
		None if account_id else email[:254],
		{"level": reservation.closed_level, "seconds": reservation.closed_seconds},
	)


# Forget the failures of an email after a good login
@retry_on_deadlock
def clear(email: str) -> None:
	with transaction() as tx:
		tx.execute("DELETE FROM login_throttle WHERE email_hash = %s", (_key(email),))


# Remove an active lock and return False when the email was not locked
@retry_on_deadlock
def unlock(email: str, account_id: int, admin_id: int) -> bool:

	# The condition on the lock makes a second unlock change nothing
	with transaction() as tx:
		changed = tx.execute(
			"DELETE FROM login_throttle WHERE email_hash = %s AND locked_until > NOW()",
			(_key(email),),
		)
		if not changed:
			return False
		audit.record(tx, "authn_account_unlocked", "success", admin_id, account_id)
		return True


# Return the end of the active lock of each email that has one, with the email as the key
def locks_of(emails: list[str]) -> dict:
	if not emails:
		return {}
	keys = {_key(email): email for email in emails}

	# Only the placeholders are joined and the hashes travel as parameters
	placeholders = ", ".join(["%s"] * len(keys))
	rows = query(
		f"SELECT email_hash, locked_until FROM login_throttle WHERE locked_until > NOW() AND email_hash IN ({placeholders})",
		tuple(keys),
	)
	return {keys[row["email_hash"]]: row["locked_until"] for row in rows}

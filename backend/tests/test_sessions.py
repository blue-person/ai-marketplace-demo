# Import libraries
import hashlib
from contextlib import contextmanager

# Import modules
from app import sessions


# Transaction that records the statements and answers the read of the account
class FakeTx:
	def __init__(self, changed=1):
		self.changed = changed
		self.executed = []
		self.inserted = []
		self.reads = []

	def query(self, sql, params=(), one=False):
		self.reads.append((sql, params))
		return {"account_id": 7}

	def execute(self, sql, params=()):
		self.executed.append((sql, params))
		return self.changed

	def insert(self, sql, params=()):
		self.inserted.append((sql, params))
		return 0


# Use the fake transaction in place of the real one
def _use(monkeypatch, tx):
	@contextmanager
	def fake_transaction():
		yield tx

	monkeypatch.setattr(sessions, "transaction", fake_transaction)


# The table receives the hash of the token and the browser receives the token
def test_start_stores_only_the_hash_of_the_token(monkeypatch):
	tx = FakeTx()
	_use(monkeypatch, tx)
	token = sessions.start(7)
	assert tx.inserted[0][1] == (hashlib.sha256(token.encode()).hexdigest(), 7)
	assert token not in str(tx.inserted)
	assert len(token) >= 43


# Two sessions never share a token
def test_every_session_has_its_own_token(monkeypatch):
	_use(monkeypatch, FakeTx())
	assert len({sessions.start(7) for _ in range(50)}) == 50


# A session that the update accepted gives its account
def test_a_valid_session_gives_its_account(monkeypatch):
	tx = FakeTx(changed=1)
	_use(monkeypatch, tx)
	assert sessions.touch("token") == 7


# The update carries both limits and refuses a closed session
def test_the_update_checks_the_idle_limit_the_absolute_limit_and_the_closing(monkeypatch):
	tx = FakeTx()
	_use(monkeypatch, tx)
	sessions.touch("token")
	sql, params = tx.executed[0]
	assert "revoked_at IS NULL" in sql
	assert "last_seen_at > NOW(6) - INTERVAL %s SECOND" in sql
	assert "created_at > NOW(6) - INTERVAL %s SECOND" in sql
	assert params[1:] == (sessions.IDLE_TIMEOUT_SECONDS, sessions.ABSOLUTE_TIMEOUT_SECONDS)


# A session that the update refused gives no account and nothing else is read
def test_a_refused_session_gives_no_account(monkeypatch):
	tx = FakeTx(changed=0)
	_use(monkeypatch, tx)
	assert sessions.touch("token") is None
	assert tx.reads == []


# The limits are the ones of the standard
def test_the_limits_are_fifteen_minutes_idle_and_eight_hours_in_total():
	assert sessions.IDLE_TIMEOUT_SECONDS == 15 * 60
	assert sessions.ABSOLUTE_TIMEOUT_SECONDS == 8 * 60 * 60


# Closing a session marks it as revoked only once
def test_end_marks_the_session_as_revoked(monkeypatch):
	tx = FakeTx()
	_use(monkeypatch, tx)
	sessions.end("token")
	sql, params = tx.executed[0]
	assert "SET revoked_at = NOW(6)" in sql
	assert "revoked_at IS NULL" in sql
	assert params == (hashlib.sha256(b"token").hexdigest(),)

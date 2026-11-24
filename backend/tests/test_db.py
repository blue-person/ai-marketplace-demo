# Import libraries
import pytest
from mysql.connector import errors

# Import modules
from app import db

# Constants
DEADLOCK = errors.InternalError(msg="Deadlock found", errno=1213, sqlstate="40001")
LOCK_TIMEOUT = errors.DatabaseError(msg="Lock wait timeout exceeded", errno=1205)
DUPLICATE = errors.IntegrityError(msg="Duplicate entry", errno=1062, sqlstate="23000")
MISSING_PARENT = errors.IntegrityError(msg="Foreign key fails", errno=1452, sqlstate="23000")


# Connection double that records the calls of the transaction helper
class FakeConnection:
	def __init__(self, rowcount=1, lastrowid=7):
		self.calls = []
		self._rowcount = rowcount
		self._lastrowid = lastrowid

	def start_transaction(self):
		self.calls.append("start")

	def commit(self):
		self.calls.append("commit")

	def rollback(self):
		self.calls.append("rollback")

	def cursor(self, **_options):
		return FakeCursor(self._rowcount, self._lastrowid)


# Cursor double that reports a fixed result for every statement
class FakeCursor:
	def __init__(self, rowcount, lastrowid):
		self.rowcount = rowcount
		self.lastrowid = lastrowid

	def execute(self, _sql, _params):
		pass

	def close(self):
		pass


# Use a connection double and skip the real waiting time of the retries
@pytest.fixture
def fake(monkeypatch):
	connection = FakeConnection()
	monkeypatch.setattr(db, "connection", lambda: connection)
	monkeypatch.setattr("time.sleep", lambda _seconds: None)
	return connection


# Function double that raises the given errors in order and then returns
def failing_then_ok(*failures):
	state = {"calls": 0}

	@db.retry_on_deadlock
	def operation():
		state["calls"] += 1
		if state["calls"] <= len(failures):
			raise failures[state["calls"] - 1]
		return "done"

	return operation, state


# A block that ends well is committed after the transaction starts
def test_commits_when_the_block_ends_without_error(fake):
	with db.transaction():
		pass
	assert fake.calls == ["start", "commit"]


# Any error rolls the work back and reaches the caller unchanged
def test_rolls_back_and_reraises_when_the_block_fails(fake):
	with pytest.raises(ValueError), db.transaction():
		raise ValueError("boom")
	assert fake.calls == ["start", "rollback"]


# A repeated unique key becomes the neutral error after a rollback
def test_turns_a_duplicate_key_into_duplicate_error_after_rollback(fake):
	with pytest.raises(db.DuplicateError), db.transaction():
		raise DUPLICATE
	assert fake.calls == ["start", "rollback"]


# Other integrity errors keep their own type
def test_keeps_other_integrity_errors_unchanged(fake):
	with pytest.raises(errors.IntegrityError) as raised, db.transaction():
		raise MISSING_PARENT
	assert raised.value.errno == 1452


# The caller learns how many rows the conditional write changed
def test_execute_returns_the_number_of_changed_rows(monkeypatch):
	connection = FakeConnection(rowcount=0)
	monkeypatch.setattr(db, "connection", lambda: connection)
	with db.transaction() as tx:
		assert tx.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (1, 1)) == 0


# The caller learns the id of the inserted row
def test_insert_returns_the_new_row_id(monkeypatch):
	connection = FakeConnection(lastrowid=42)
	monkeypatch.setattr(db, "connection", lambda: connection)
	with db.transaction() as tx:
		assert tx.insert("INSERT INTO transfers (amount) VALUES (%s)", (1,)) == 42


# One deadlock is absorbed and the second attempt gives the result
def test_repeats_the_operation_once_after_a_deadlock(fake):
	operation, state = failing_then_ok(DEADLOCK)
	assert operation() == "done"
	assert state["calls"] == 2


# Three deadlocks in a row end with the original error and exactly three attempts
def test_gives_up_after_three_deadlocks_and_raises_the_original_error(fake):
	operation, state = failing_then_ok(DEADLOCK, DEADLOCK, DEADLOCK, DEADLOCK)
	with pytest.raises(errors.InternalError) as raised:
		operation()
	assert raised.value.errno == 1213
	assert state["calls"] == 3


# A lock wait timeout is not a deadlock so it is not repeated
def test_does_not_repeat_a_lock_wait_timeout(fake):
	operation, state = failing_then_ok(LOCK_TIMEOUT)
	with pytest.raises(errors.DatabaseError):
		operation()
	assert state["calls"] == 1


# A duplicate key would fail the same way again so it is not repeated
def test_does_not_repeat_a_duplicate_key_error(fake):
	operation, state = failing_then_ok(DUPLICATE)
	with pytest.raises(errors.IntegrityError):
		operation()
	assert state["calls"] == 1

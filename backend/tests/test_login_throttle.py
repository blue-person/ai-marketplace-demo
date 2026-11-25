# Import libraries
import hashlib
from contextlib import contextmanager
import pytest

# Import modules
from app import login_throttle

# Constants
EMAIL = "dev1@marketplace.test"
KEY = hashlib.sha256(EMAIL.encode()).hexdigest()
OPEN_ROW = {"failures": 0, "lock_level": 0, "locked": 0, "remaining": None, "stale": 0}


# Transaction that records the statements and answers the read of the counter with one row
class FakeTx:
	def __init__(self, row=None, changed=1):
		self.row = row
		self.changed = changed
		self.executed = []

	def query(self, sql, params=(), one=False):
		return self.row

	def execute(self, sql, params=()):
		self.executed.append((sql, params))
		return self.changed


# Use the fake transaction and record the audit events
def _use(monkeypatch, tx):
	events = []

	@contextmanager
	def fake_transaction():
		yield tx

	monkeypatch.setattr(login_throttle, "transaction", fake_transaction)
	monkeypatch.setattr(login_throttle.audit, "record", lambda *args, **kwargs: events.append((args[1], args[2:])))
	return events


# Statements of the fake transaction that change the counter, without the insert of the row and the purge
def _updates(tx):
	return [item for item in tx.executed if item[0].startswith("UPDATE")]


# The lock starts at 30 minutes and doubles with each level up to one day
@pytest.mark.parametrize(
	"level, seconds", [(1, 1800), (2, 3600), (3, 7200), (4, 14400), (5, 28800), (6, 57600), (7, 86400), (255, 86400)]
)
def test_the_lock_doubles_with_each_level_up_to_one_day(level, seconds):
	assert login_throttle.lock_seconds(level) == seconds


# The first lock is never shorter than the 30 minutes of the standard
def test_the_first_lock_lasts_at_least_thirty_minutes():
	assert login_throttle.lock_seconds(1) >= 30 * 60


# An attempt below the limit is counted and allowed
def test_an_attempt_below_the_limit_is_counted(monkeypatch):
	tx = FakeTx({**OPEN_ROW, "failures": 3})
	_use(monkeypatch, tx)
	assert login_throttle.reserve_attempt(EMAIL) == login_throttle.Reservation()
	assert _updates(tx) == [("UPDATE login_throttle SET failures = %s WHERE email_hash = %s", (4, KEY))]


# The tenth attempt is allowed and closes the lock at level one without writing any event yet
def test_the_tenth_attempt_closes_the_lock(monkeypatch):
	tx = FakeTx({**OPEN_ROW, "failures": 9})
	events = _use(monkeypatch, tx)
	reservation = login_throttle.reserve_attempt(EMAIL)
	assert reservation == login_throttle.Reservation(closed_level=1, closed_seconds=1800)
	assert reservation.seconds_left is None
	sql, params = _updates(tx)[0]
	assert "locked_until" in sql
	assert params == (1, 1800, KEY)
	assert events == []


# The next lock of an email that was locked before lasts twice as long
def test_the_next_lock_is_longer(monkeypatch):
	tx = FakeTx({**OPEN_ROW, "failures": 9, "lock_level": 2})
	_use(monkeypatch, tx)
	reservation = login_throttle.reserve_attempt(EMAIL)
	assert _updates(tx)[0][1] == (3, 7200, KEY)
	assert (reservation.closed_level, reservation.closed_seconds) == (3, 7200)


# A locked email gets the seconds left and the attempt is not counted
def test_a_locked_email_is_refused_without_counting(monkeypatch):
	tx = FakeTx({**OPEN_ROW, "lock_level": 1, "locked": 1, "remaining": 900})
	events = _use(monkeypatch, tx)
	assert login_throttle.reserve_attempt(EMAIL) == login_throttle.Reservation(seconds_left=900)
	assert _updates(tx) == []
	assert events == []


# A lock that ends in less than a second still reports one second
def test_the_seconds_left_are_at_least_one(monkeypatch):
	_use(monkeypatch, FakeTx({**OPEN_ROW, "lock_level": 1, "locked": 1, "remaining": 0}))
	assert login_throttle.reserve_attempt(EMAIL).seconds_left == 1


# Failures of an old window are forgotten and the attempt counts as the first
def test_failures_of_an_old_window_are_forgotten(monkeypatch):
	tx = FakeTx({**OPEN_ROW, "failures": 9, "stale": 1})
	_use(monkeypatch, tx)
	assert login_throttle.reserve_attempt(EMAIL) == login_throttle.Reservation()
	assert _updates(tx) == [("UPDATE login_throttle SET failures = %s WHERE email_hash = %s", (1, KEY))]


# The event of a lock is written only when the attempt that closed it failed
def test_the_event_of_a_lock_is_written_after_a_failed_attempt(monkeypatch):
	events = []
	monkeypatch.setattr(login_throttle.audit, "record_alone", lambda *args: events.append(args))
	login_throttle.record_lock(login_throttle.Reservation(closed_level=2, closed_seconds=3600), EMAIL, 5)
	assert events == [("authn_account_locked", "failure", None, 5, None, {"level": 2, "seconds": 3600})]


# An attempt that did not close a lock writes nothing
def test_an_attempt_that_closed_no_lock_writes_no_event(monkeypatch):
	events = []
	monkeypatch.setattr(login_throttle.audit, "record_alone", lambda *args: events.append(args))
	login_throttle.record_lock(login_throttle.Reservation(), EMAIL, 5)
	login_throttle.record_lock(login_throttle.Reservation(seconds_left=30), EMAIL, 5)
	assert events == []


# The event of an email without account carries the typed text as its label
def test_the_lock_event_of_an_unknown_email_has_the_label(monkeypatch):
	events = []
	monkeypatch.setattr(login_throttle.audit, "record_alone", lambda *args: events.append(args))
	login_throttle.record_lock(login_throttle.Reservation(closed_level=1, closed_seconds=1800), "nobody@x.test", None)
	assert events[0][3:5] == (None, "nobody@x.test")


# Old rows are deleted only when the attempt created a new row
@pytest.mark.parametrize("created, purged", [(1, True), (0, False)])
def test_old_rows_are_deleted_when_a_row_is_created(monkeypatch, created, purged):
	tx = FakeTx(OPEN_ROW, changed=created)
	_use(monkeypatch, tx)
	login_throttle.reserve_attempt(EMAIL)
	assert any(sql.startswith("DELETE") for sql, _ in tx.executed) is purged


# The table holds the hash of the email and not the email
def test_the_email_is_stored_as_a_hash(monkeypatch):
	tx = FakeTx(OPEN_ROW)
	_use(monkeypatch, tx)
	login_throttle.reserve_attempt(EMAIL)
	assert all(EMAIL not in str(params) for _, params in tx.executed)
	assert tx.executed[0][1] == (KEY,)


# A good login deletes the counter of the email
def test_clear_deletes_the_counter(monkeypatch):
	tx = FakeTx()
	_use(monkeypatch, tx)
	login_throttle.clear(EMAIL)
	assert tx.executed == [("DELETE FROM login_throttle WHERE email_hash = %s", (KEY,))]


# An unlock writes the event only when a lock was removed
@pytest.mark.parametrize("changed, expected, events", [(1, True, ["authn_account_unlocked"]), (0, False, [])])
def test_unlock_writes_the_event_only_when_it_removed_a_lock(monkeypatch, changed, expected, events):
	recorded = _use(monkeypatch, FakeTx(changed=changed))
	assert login_throttle.unlock(EMAIL, 5, 1) is expected
	assert [name for name, _ in recorded] == events


# Without emails there is nothing to read and the locks come back by email
def test_locks_of_returns_the_end_of_each_lock_by_email(monkeypatch):
	assert login_throttle.locks_of([]) == {}
	monkeypatch.setattr(
		login_throttle, "query", lambda sql, params=(), one=False: [{"email_hash": KEY, "locked_until": "later"}]
	)
	assert login_throttle.locks_of([EMAIL, "other@x.test"]) == {EMAIL: "later"}

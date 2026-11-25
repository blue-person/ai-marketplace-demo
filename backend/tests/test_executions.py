# Import libraries
from contextlib import contextmanager
from decimal import Decimal
import pytest
from werkzeug.exceptions import BadRequest, Conflict, NotFound, UnprocessableEntity

# Import modules
from app import executions, external_api
from app.db import DuplicateError
from app.executions import Charge
from app.money import NotEnoughBalanceError

# Constants
KEY = "0b8f4c1e-6a52-4c3a-9d7e-2f1a5b6c7d8e"


# Calls that the flow of an execution makes, in order
class Recorder:
	def __init__(self):
		self.calls = []

	def add(self, name, result=None):
		def fake(*args, **kwargs):
			self.calls.append((name, args))
			if isinstance(result, Exception):
				raise result
			return result

		return fake


# Replace the database and the model with fakes and return the recorder of the calls
def _fake_flow(monkeypatch, model_result="The answer", charge_result=None):
	recorder = Recorder()
	monkeypatch.setattr(executions, "expire_stale", recorder.add("expire"))
	monkeypatch.setattr(executions, "_platform_id", recorder.add("platform_id", 99))
	monkeypatch.setattr(executions, "_charge", recorder.add("charge", charge_result or Charge(7, "a/one")))
	monkeypatch.setattr(executions.external_api, "chat_completion", recorder.add("model", model_result))
	monkeypatch.setattr(executions, "_complete", recorder.add("complete", True))
	monkeypatch.setattr(executions, "_fail", recorder.add("fail", True))
	monkeypatch.setattr(
		executions, "_read_execution", lambda account_id, execution_id: {"id": execution_id, "failure_reason": None}
	)
	return recorder


# The names of the calls in the order they happened
def _names(recorder):
	return [name for name, _args in recorder.calls]


# A key in any case is returned in the canonical lowercase form
def test_the_key_is_returned_in_canonical_form():
	assert executions.read_idempotency_key(f"  {KEY.upper()}  ") == KEY


# A missing or malformed key is refused with a 400
@pytest.mark.parametrize("value", [None, "", "   ", "abc", KEY + "0", "not-a-uuid-at-all-not-a-uuid-at-all"])
def test_a_missing_or_malformed_key_is_refused(value):
	with pytest.raises(BadRequest):
		executions.read_idempotency_key(value)


# A prompt is trimmed and one of the limit length is accepted
def test_a_prompt_is_trimmed_and_the_limit_is_accepted():
	assert executions.read_prompt({"prompt": "  hello  "}) == "hello"
	assert len(executions.read_prompt({"prompt": "x" * executions.MAX_PROMPT_LENGTH})) == executions.MAX_PROMPT_LENGTH


# A prompt that is missing, empty, not a text or too long is refused with a 400
@pytest.mark.parametrize("value", [None, "", "   ", 5, ["a"], {"a": 1}, "x" * (executions.MAX_PROMPT_LENGTH + 1)])
def test_a_bad_prompt_is_refused(value):
	with pytest.raises(BadRequest):
		executions.read_prompt({"prompt": value})


# The fingerprint changes with the agent and with the prompt
def test_the_fingerprint_depends_on_the_agent_and_the_prompt():
	base = executions.request_hash(1, "hello")
	assert base == executions.request_hash(1, "hello")
	assert base != executions.request_hash(2, "hello")
	assert base != executions.request_hash(1, "hello ")
	assert len(base) == 64


# A good answer of the model is saved and the user is not refunded
def test_a_good_answer_completes_the_execution(monkeypatch):
	recorder = _fake_flow(monkeypatch)
	execution, created = executions.run_execution(4, 3, KEY, "hello")
	assert created is True
	assert execution["id"] == 7
	assert _names(recorder) == ["expire", "platform_id", "charge", "model", "complete"]
	assert dict(recorder.calls)["complete"] == (7, "The answer", 99)


# A failure of the model refunds the execution and does not pay anybody
def test_a_failure_of_the_model_fails_the_execution(monkeypatch):
	recorder = _fake_flow(monkeypatch, model_result=external_api.ExternalApiError("down"))
	executions.run_execution(4, 3, KEY, "hello")
	assert _names(recorder) == ["expire", "platform_id", "charge", "model", "fail"]
	assert dict(recorder.calls)["fail"] == (7, "service_unavailable")


# The model is never called when the charge fails
def test_the_model_is_not_called_when_the_charge_fails(monkeypatch):
	recorder = _fake_flow(monkeypatch, charge_result=BadRequest())
	with pytest.raises(BadRequest):
		executions.run_execution(4, 3, KEY, "hello")
	assert "model" not in _names(recorder)


# The charge is made before the model is called and the model before the payment
def test_the_model_is_called_between_the_charge_and_the_payment(monkeypatch):
	recorder = _fake_flow(monkeypatch)
	executions.run_execution(4, 3, KEY, "hello")
	names = _names(recorder)
	assert names.index("charge") < names.index("model") < names.index("complete")


# A repeated key with the same request returns the saved execution and calls nothing else
def test_a_repeated_key_returns_the_saved_execution(monkeypatch):
	recorder = _fake_flow(monkeypatch, charge_result=DuplicateError())
	saved = {"id": 7, "request_hash": executions.request_hash(3, "hello"), "status": "completed"}
	monkeypatch.setattr(executions, "query", lambda sql, params=(), one=False: saved)
	execution, created = executions.run_execution(4, 3, KEY, "hello")
	assert created is False
	assert execution["id"] == 7
	assert _names(recorder) == ["expire", "platform_id", "charge"]


# A repeated key with another prompt is refused with a 422
def test_a_repeated_key_with_another_request_is_refused(monkeypatch):
	_fake_flow(monkeypatch, charge_result=DuplicateError())
	saved = {"id": 7, "request_hash": executions.request_hash(3, "other"), "status": "completed"}
	monkeypatch.setattr(executions, "query", lambda sql, params=(), one=False: saved)
	with pytest.raises(UnprocessableEntity):
		executions.run_execution(4, 3, KEY, "hello")


# A repeated key while the first request still runs is refused with a 409
def test_a_repeated_key_while_running_is_refused(monkeypatch):
	_fake_flow(monkeypatch, charge_result=DuplicateError())
	saved = {"id": 7, "request_hash": executions.request_hash(3, "hello"), "status": "pending"}
	monkeypatch.setattr(executions, "query", lambda sql, params=(), one=False: saved)
	with pytest.raises(Conflict):
		executions.run_execution(4, 3, KEY, "hello")


# The failure reasons of the table have a label for the user
def test_every_failure_reason_has_a_label():
	assert set(executions.FAILURE_REASONS) == {"service_unavailable", "expired"}


# Transaction that records the statements and answers the reads with the rows it was given
class FakeTx:
	def __init__(self, reads=None, changed=1):
		self.reads = reads or {}
		self.changed = changed
		self.executed = []
		self.inserted = []

	def query(self, sql, params=(), one=False):
		for part, row in self.reads.items():
			if part in sql:
				return row
		return None if one else []

	def execute(self, sql, params=()):
		self.executed.append((sql, params))
		return self.changed

	def insert(self, sql, params=()):
		self.inserted.append((sql, params))
		return 7


# Use the fake transaction in place of the real one and record the audit events
def _use(monkeypatch, tx):
	events = []

	@contextmanager
	def fake_transaction():
		yield tx

	monkeypatch.setattr(executions, "transaction", fake_transaction)
	monkeypatch.setattr(executions.audit, "record", lambda *args, **kwargs: events.append(args[1]))
	return events


AGENT = {"developer_id": 3, "price_usd": Decimal("0.50"), "model": "a/one"}
PENDING = {"account_id": 4, "agent_id": 3, "developer_id": 3, "cost_usd": Decimal("0.50"), "status": "pending"}


# The price is taken with a conditional update and the charge is written in the ledger
def test_the_charge_is_conditional_and_written_in_the_ledger(monkeypatch):
	tx = FakeTx({"FROM agents": AGENT})
	_use(monkeypatch, tx)
	assert executions._charge(4, 3, KEY, "h" * 64, "hello") == Charge(7, "a/one")
	sql, params = tx.executed[0]
	assert "balance >= %s" in sql
	assert params == (Decimal("0.50"), 4, Decimal("0.50"))
	assert tx.inserted[1][1] == (4, Decimal("-0.50"), 7)
	assert "'agent_execution'" in tx.inserted[1][0]


# A user that cannot pay gets an error so the transaction is undone
def test_a_balance_that_is_not_enough_raises_an_error(monkeypatch):
	_use(monkeypatch, FakeTx({"FROM agents": AGENT}, changed=0))
	with pytest.raises(NotEnoughBalanceError):
		executions._charge(4, 3, KEY, "h" * 64, "hello")


# The developer runs the own agent with no charge and no ledger entry
def test_the_developer_runs_the_own_agent_for_free(monkeypatch):
	tx = FakeTx({"FROM agents": AGENT})
	_use(monkeypatch, tx)
	executions._charge(3, 3, KEY, "h" * 64, "hello")
	assert tx.executed == []
	assert len(tx.inserted) == 1
	assert tx.inserted[0][1][-1] == 0


# An agent that does not exist or is not approved is a 404 and nothing is written
def test_an_unknown_agent_is_a_404(monkeypatch):
	tx = FakeTx()
	_use(monkeypatch, tx)
	with pytest.raises(NotFound):
		executions._charge(4, 3, KEY, "h" * 64, "hello")
	assert tx.inserted == []


# A completed execution pays 80 percent to the developer and 20 percent to the platform
def test_a_completed_execution_pays_the_developer_and_the_platform(monkeypatch):
	tx = FakeTx({"FROM executions": PENDING})
	events = _use(monkeypatch, tx)
	assert executions._complete(7, "answer", 99) is True
	assert tx.executed[0][1][:3] == ("answer", Decimal("0.4000"), Decimal("0.1000"))
	credits = [(params[0], params[1], params[2]) for _sql, params in tx.inserted]
	assert credits == [(3, Decimal("0.4000"), "agent_earning"), (99, Decimal("0.1000"), "platform_fee")]
	assert events == ["agent_executed"]


# A free execution is completed without moving any credit
def test_a_free_execution_moves_no_credit(monkeypatch):
	tx = FakeTx({"FROM executions": {**PENDING, "account_id": 3, "cost_usd": Decimal("0.00")}})
	_use(monkeypatch, tx)
	assert executions._complete(7, "answer", 99) is True
	assert tx.inserted == []
	assert tx.executed[0][1][1:3] == (None, None)


# An execution that was closed meanwhile is not paid a second time
@pytest.mark.parametrize("status", ["completed", "failed"])
def test_a_closed_execution_is_not_paid_again(monkeypatch, status):
	tx = FakeTx({"FROM executions": {**PENDING, "status": status}})
	events = _use(monkeypatch, tx)
	assert executions._complete(7, "answer", 99) is False
	assert tx.executed == []
	assert tx.inserted == []
	assert events == []


# A failed execution returns the whole price to the user with a new entry of the ledger
def test_a_failed_execution_refunds_the_user(monkeypatch):
	tx = FakeTx({"FROM executions": PENDING})
	events = _use(monkeypatch, tx)
	assert executions._fail(7, "service_unavailable") is True
	assert tx.inserted == [
		(
			"INSERT INTO ledger_entries (account_id, amount, entry_type, execution_id) VALUES (%s, %s, %s, %s)",
			(4, Decimal("0.50"), "agent_refund", 7),
		)
	]
	assert events == ["agent_execution_failed"]


# An expired execution has its own event and a free one has nothing to refund
def test_an_expired_free_execution_refunds_nothing(monkeypatch):
	tx = FakeTx({"FROM executions": {**PENDING, "cost_usd": Decimal("0.00")}})
	events = _use(monkeypatch, tx)
	assert executions._fail(7, "expired") is True
	assert tx.inserted == []
	assert events == ["agent_execution_expired"]


# An execution that was closed meanwhile is not refunded a second time
@pytest.mark.parametrize("status", ["completed", "failed"])
def test_a_closed_execution_is_not_refunded_again(monkeypatch, status):
	tx = FakeTx({"FROM executions": {**PENDING, "status": status}})
	events = _use(monkeypatch, tx)
	assert executions._fail(7, "expired") is False
	assert tx.executed == []
	assert tx.inserted == []
	assert events == []

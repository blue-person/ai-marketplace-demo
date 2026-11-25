# Import libraries
import re
import uuid
from decimal import Decimal
from pathlib import Path
import pytest
from werkzeug.exceptions import BadRequest, NotFound

# Import modules
from app import schedules
from app.money import NotEnoughBalanceError
from app.schedules import Claim

# Constants
SCHEMA = Path(__file__).resolve().parents[2] / "database" / "init" / "08-schedules.sql"
RECURRING = {"agent_id": 3, "kind": "recurring", "prompt": "Say hello", "every": 1, "unit": "hours"}
CONDITIONAL = {
	"agent_id": 3,
	"kind": "conditional",
	"prompt": "Say hello",
	"threshold_usd": "50.00",
	"cooldown_every": 1,
	"cooldown_unit": "hours",
}
CLAIM = Claim(account_id=4, agent_id=3, prompt="Say hello", occurrence=1700000000)


# Return the request with some fields changed
def _with(base: dict, **changes) -> dict:
	return {**base, **changes}


# A recurring schedule has an interval in seconds and nothing of the conditional kind
def test_a_recurring_schedule_is_converted_to_seconds():
	schedule = schedules.validate_schedule(RECURRING)
	assert schedule["interval_seconds"] == 3600
	assert schedule["threshold_usd"] is None and schedule["cooldown_seconds"] is None


# A conditional schedule has a threshold and a cooldown and no interval
def test_a_conditional_schedule_has_a_threshold_and_a_cooldown():
	schedule = schedules.validate_schedule(CONDITIONAL)
	assert schedule["threshold_usd"] == Decimal("50.00")
	assert schedule["cooldown_seconds"] == 3600
	assert schedule["interval_seconds"] is None


# The fields of the other kind are ignored so the row respects the checks of the table
def test_the_fields_of_the_other_kind_are_ignored():
	schedule = schedules.validate_schedule(
		_with(RECURRING, threshold_usd="5.00", cooldown_every=1, cooldown_unit="days")
	)
	assert schedule["threshold_usd"] is None and schedule["cooldown_seconds"] is None


# The units are minutes, hours and days and the limits are inclusive
@pytest.mark.parametrize(
	("every", "unit", "seconds"),
	[(5, "minutes", 300), (2, "hours", 7200), (30, "days", 2592000), (720, "hours", 2592000)],
)
def test_the_units_and_the_limits_of_the_interval_are_accepted(every, unit, seconds):
	assert schedules.validate_schedule(_with(RECURRING, every=every, unit=unit))["interval_seconds"] == seconds


# An interval that is not a whole number, has no known unit or is out of the limits is refused
@pytest.mark.parametrize(
	("every", "unit"),
	[
		(4, "minutes"),
		(31, "days"),
		(721, "hours"),
		(0, "hours"),
		(-1, "hours"),
		(1.5, "hours"),
		(True, "hours"),
		("1", "hours"),
		(None, "hours"),
		(1, "weeks"),
		(1, None),
	],
)
def test_a_bad_interval_is_refused(every, unit):
	with pytest.raises(BadRequest):
		schedules.validate_schedule(_with(RECURRING, every=every, unit=unit))


# A cooldown has a minimum of ten minutes
@pytest.mark.parametrize(("every", "unit"), [(9, "minutes"), (31, "days"), (0, "minutes"), (True, "hours")])
def test_a_bad_cooldown_is_refused(every, unit):
	with pytest.raises(BadRequest):
		schedules.validate_schedule(_with(CONDITIONAL, cooldown_every=every, cooldown_unit=unit))
	assert (
		schedules.validate_schedule(_with(CONDITIONAL, cooldown_every=10, cooldown_unit="minutes"))["cooldown_seconds"]
		== 600
	)


# A threshold must be a positive amount with at most two decimals
@pytest.mark.parametrize(
	"value", [None, "", "abc", "0", "0.00", "-5", "1.234", "NaN", "Infinity", "99999999999.00", [5]]
)
def test_a_bad_threshold_is_refused(value):
	with pytest.raises(BadRequest):
		schedules.validate_schedule(_with(CONDITIONAL, threshold_usd=value))


# The agent, the kind and the prompt are required
@pytest.mark.parametrize(
	"changes",
	[
		{"agent_id": None},
		{"agent_id": 0},
		{"agent_id": True},
		{"agent_id": "3"},
		{"kind": "daily"},
		{"kind": None},
		{"prompt": ""},
		{"prompt": "   "},
		{"prompt": 5},
		{"prompt": "x" * 2001},
	],
)
def test_the_agent_the_kind_and_the_prompt_are_required(changes):
	with pytest.raises(BadRequest):
		schedules.validate_schedule(_with(RECURRING, **changes))


# The key of an occurrence is a UUID that is the same for the same occurrence and different for another one
def test_the_key_of_an_occurrence_is_stable_and_different_for_each_occurrence():
	key = schedules.occurrence_key(7, 1700000000)
	assert key == schedules.occurrence_key(7, 1700000000)
	assert str(uuid.UUID(key)) == key
	assert key != schedules.occurrence_key(7, 1700003600)
	assert key != schedules.occurrence_key(8, 1700000000)


# The limits of the code are the same ones that the table checks
def test_the_limits_match_the_checks_of_the_table():
	text = SCHEMA.read_text()
	interval = re.search(r"interval_seconds BETWEEN (\d+) AND (\d+)", text).groups()
	cooldown = re.search(r"cooldown_seconds BETWEEN (\d+) AND (\d+)", text).groups()
	assert (int(interval[0]), int(interval[1])) == (schedules.MIN_INTERVAL_SECONDS, schedules.MAX_PERIOD_SECONDS)
	assert (int(cooldown[0]), int(cooldown[1])) == (schedules.MIN_COOLDOWN_SECONDS, schedules.MAX_PERIOD_SECONDS)
	assert f"consecutive_failures <= {schedules.MAX_FAILURES_IN_A_ROW}" in text


# Calls that a launch makes, in order
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


# Replace the claim, the execution and the saving with fakes and return the recorder of the calls
def _fake_launch(monkeypatch, claim=CLAIM, run_result=({"id": 11, "status": "completed"}, True)):
	recorder = Recorder()
	monkeypatch.setattr(schedules, "_claim", recorder.add("claim", claim))
	monkeypatch.setattr(schedules.executions, "run_execution", recorder.add("run", run_result))
	monkeypatch.setattr(schedules, "_save_result", recorder.add("save"))
	return recorder


# The names of the calls in the order they happened
def _names(recorder):
	return [name for name, _args in recorder.calls]


# A schedule that is not due is not launched and nothing is saved
def test_a_schedule_that_is_not_due_does_nothing(monkeypatch):
	recorder = _fake_launch(monkeypatch, claim=None)
	assert schedules.launch(7, 99) is None
	assert _names(recorder) == ["claim"]


# A launch runs the agent with the key of the occurrence and saves the outcome after the run
def test_a_launch_runs_the_agent_with_the_key_of_the_occurrence(monkeypatch):
	recorder = _fake_launch(monkeypatch)
	assert schedules.launch(7, 99) == "completed"
	assert _names(recorder) == ["claim", "run", "save"]
	run = dict(recorder.calls)["run"]
	assert run == (4, 3, schedules.occurrence_key(7, 1700000000), "Say hello")
	assert dict(recorder.calls)["save"] == (7, 99, 4, "completed", 11)


# A failed execution is saved with its id so the user can read it
def test_a_failed_execution_is_saved_with_its_id(monkeypatch):
	recorder = _fake_launch(monkeypatch, run_result=({"id": 12, "status": "failed"}, True))
	assert schedules.launch(7, 99) == "failed"
	assert dict(recorder.calls)["save"] == (7, 99, 4, "failed", 12)


# A balance that is not enough is saved as a skipped launch without an execution
def test_a_balance_that_is_not_enough_is_saved_without_an_execution(monkeypatch):
	recorder = _fake_launch(monkeypatch, run_result=NotEnoughBalanceError())
	assert schedules.launch(7, 99) == "not_enough_balance"
	assert dict(recorder.calls)["save"] == (7, 99, 4, "not_enough_balance", None)


# An agent that is not approved any more is saved as a skipped launch
def test_an_agent_that_is_not_available_is_saved_as_skipped(monkeypatch):
	recorder = _fake_launch(monkeypatch, run_result=NotFound())
	assert schedules.launch(7, 99) == "agent_unavailable"
	assert dict(recorder.calls)["save"] == (7, 99, 4, "agent_unavailable", None)


# The labels explain the pause reason and the last outcome and are empty when there is none
def test_the_labels_of_a_schedule_are_added():
	described = schedules._describe({"pause_reason": "failures", "last_outcome": "not_enough_balance"})
	assert described["pause_label"] == schedules.PAUSE_LABELS["failures"]
	assert described["outcome_label"] == schedules.OUTCOME_LABELS["not_enough_balance"]
	empty = schedules._describe({"pause_reason": None, "last_outcome": None})
	assert empty["pause_label"] is None and empty["outcome_label"] is None

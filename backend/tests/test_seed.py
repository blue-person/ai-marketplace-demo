# Import libraries
from decimal import Decimal
import pytest

# Import modules
from app.agents import REJECTION_REASONS, validate_submission
from app.config import load_case
from app.seed import read_service_key


# A key of 32 characters is the shortest that is accepted
def test_accepts_a_service_key_of_32_characters(monkeypatch):
	monkeypatch.setenv("ROBOT_KEY", "k" * 32)
	assert read_service_key("ROBOT_KEY") == "k" * 32


# A key of 31 characters is refused
def test_refuses_a_service_key_of_31_characters(monkeypatch):
	monkeypatch.setenv("ROBOT_KEY", "k" * 31)
	with pytest.raises(SystemExit):
		read_service_key("ROBOT_KEY")


# A missing key is refused
def test_refuses_a_missing_service_key(monkeypatch):
	monkeypatch.delenv("ROBOT_KEY", raising=False)
	with pytest.raises(SystemExit):
		read_service_key("ROBOT_KEY")


# The placeholder of the example file is too short to be accepted
def test_refuses_the_placeholder_of_the_example_file(monkeypatch):
	monkeypatch.setenv("ROBOT_KEY", "change-me")
	with pytest.raises(SystemExit):
		read_service_key("ROBOT_KEY")


# The agents of the case follow the same rules as the ones that developers publish
def test_the_agents_of_the_case_pass_the_publication_rules(monkeypatch):
	monkeypatch.setenv("CASE", "marketplace")
	case = load_case()
	for agent in case["agents"]:
		clean = validate_submission(agent, [agent["model"]])
		assert clean["price_usd"] == Decimal(agent["price_usd"])
		assert agent["status"] in ("pending", "approved", "rejected")


# The case has an agent in each status and a reason only for the rejected one
def test_the_case_has_an_agent_in_each_status_and_a_reason_only_for_the_rejected_one(monkeypatch):
	monkeypatch.setenv("CASE", "marketplace")
	agents = load_case()["agents"]
	assert {agent["status"] for agent in agents} == {"pending", "approved", "rejected"}
	for agent in agents:
		assert (agent["status"] == "rejected") == ("rejection_reason" in agent)
		assert agent.get("rejection_reason", "other") in REJECTION_REASONS


# The developers of the agents are test accounts of the case with the developer role
def test_the_developers_of_the_agents_are_developer_accounts_of_the_case(monkeypatch):
	monkeypatch.setenv("CASE", "marketplace")
	case = load_case()
	developers = {account["email"] for account in case["test_accounts"] if account["role"] == "developer"}
	assert {agent["developer"] for agent in case["agents"]} <= developers

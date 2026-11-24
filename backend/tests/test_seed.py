# Import libraries
import pytest

# Import modules
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

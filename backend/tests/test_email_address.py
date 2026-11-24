# Import libraries
import pytest

# Import modules
from app.email_address import InvalidEmailError, normalize_email


# The normal form is all lowercase
def test_lowercases_the_whole_address():
	assert normalize_email("Dev1@Marketplace.TEST") == "dev1@marketplace.test"


# The test domains of the seed accounts must keep working
def test_accepts_a_test_domain():
	assert normalize_email("company1@marketplace.test") == "company1@marketplace.test"


# Text without an at sign is not an address
def test_refuses_text_without_an_at_sign():
	with pytest.raises(InvalidEmailError):
		normalize_email("no-at-sign")


# Two at signs are not an address
def test_refuses_two_at_signs():
	with pytest.raises(InvalidEmailError):
		normalize_email("a@@marketplace.test")


# A domain without a dot is not an address
def test_refuses_a_domain_without_a_dot():
	with pytest.raises(InvalidEmailError):
		normalize_email("a@b")


# The column holds 254 characters, so a longer address is refused
def test_refuses_an_address_longer_than_the_column():
	with pytest.raises(InvalidEmailError):
		normalize_email("x" * 250 + "@marketplace.test")

# Import modules
from app.registration import is_profile_complete, is_valid_organization


# A profile with a valid organization and a real country is complete
def test_profile_with_organization_and_country_is_complete():
	assert is_profile_complete({"organization": "Acme Labs", "country": "CO"}) is True


# Without an organization the profile is incomplete
def test_profile_without_organization_is_incomplete():
	assert is_profile_complete({"organization": None, "country": "CO"}) is False


# Without a country the profile is incomplete
def test_profile_without_country_is_incomplete():
	assert is_profile_complete({"organization": "Acme Labs", "country": None}) is False


# A country that does not exist does not complete the profile
def test_profile_with_an_unknown_country_is_incomplete():
	assert is_profile_complete({"organization": "Acme Labs", "country": "ZZ"}) is False


# Spaces alone are not an organization
def test_profile_with_a_blank_organization_is_incomplete():
	assert is_profile_complete({"organization": "   ", "country": "CO"}) is False


# An organization of one character is too short and two characters are enough
def test_organization_needs_at_least_two_characters():
	assert is_valid_organization("A") is False
	assert is_valid_organization("AB") is True


# An organization of 100 characters fits the column and 101 does not
def test_organization_accepts_at_most_one_hundred_characters():
	assert is_valid_organization("x" * 100) is True
	assert is_valid_organization("x" * 101) is False

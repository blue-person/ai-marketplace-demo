# Import modules
from app.countries import country_choices, is_valid_country


# A real ISO code is accepted
def test_accepts_an_iso_code():
	assert is_valid_country("CO") is True


# A code that does not exist is refused
def test_refuses_a_code_that_does_not_exist():
	assert is_valid_country("ZZ") is False


# The code must be written exactly as the list sends it
def test_refuses_a_lowercase_code():
	assert is_valid_country("co") is False


# An empty value is not a country
def test_refuses_an_empty_value():
	assert is_valid_country("") is False


# The list that the interface shows contains pairs that the backend accepts
def test_choices_contain_colombia_with_its_code():
	assert {"code": "CO", "name": "Colombia"} in country_choices()


# The names are sorted so the interface does not have to sort them
def test_choices_are_sorted_by_name():
	names = [choice["name"] for choice in country_choices()]
	assert names == sorted(names)

# Import libraries
import pycountry

# Constants
COUNTRY_CODES = frozenset(country.alpha_2 for country in pycountry.countries)


# Return the countries as code and name pairs sorted by name
def country_choices() -> list[dict]:
	choices = [{"code": country.alpha_2, "name": country.name} for country in pycountry.countries]
	return sorted(choices, key=lambda choice: choice["name"])


# True when the text is exactly the two letter ISO code of a country
def is_valid_country(code: str) -> bool:
	return code in COUNTRY_CODES

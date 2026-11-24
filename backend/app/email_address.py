# Import libraries
from email_validator import EmailNotValidError, validate_email


# Raised when the text is not a valid email address
class InvalidEmailError(ValueError):
	pass


# Return the address in its normal form or raise InvalidEmailError
def normalize_email(text: str) -> str:
	try:
		result = validate_email(text, check_deliverability=False, test_environment=True)
	except EmailNotValidError as error:
		raise InvalidEmailError("The email address is not valid.") from error

	# The library lowercases only the domain, so the whole address is lowercased here
	return result.normalized.lower()

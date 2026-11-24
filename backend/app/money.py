# Import libraries
from decimal import Decimal, InvalidOperation
from flask import abort

# Constants
CENT = Decimal("0.01")


# Turn a value of the request into a positive Decimal with at most two decimals and a maximum
def parse_usd(value, maximum: Decimal, label: str = "amount") -> Decimal:
	try:
		amount = Decimal(str(value).strip())
	except InvalidOperation:
		abort(400, description=f"The {label} is not a valid number.")

	# The checks run in this order because NaN cannot be compared and huge exponents cannot be rounded
	if not amount.is_finite() or not CENT <= amount <= maximum or amount != amount.quantize(CENT):
		abort(400, description=f"The {label} must be between {CENT} and {maximum} with at most two decimals.")
	return amount

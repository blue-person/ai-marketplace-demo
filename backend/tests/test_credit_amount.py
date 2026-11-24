# Import libraries
from decimal import Decimal
import pytest
from werkzeug.exceptions import BadRequest

# Import modules
from app.routes_credit import _parse_amount


# Amounts inside the range with at most two decimals are accepted
@pytest.mark.parametrize(
	"value, expected",
	[
		("5.00", Decimal("5.00")),
		("5.5", Decimal("5.5")),
		(5, Decimal(5)),
		("0.01", Decimal("0.01")),
		("9999999999.99", Decimal("9999999999.99")),
	],
)
def test_accepts_amounts_inside_the_range_with_up_to_two_decimals(value, expected):
	assert _parse_amount(value) == expected


# Amounts outside the rule are refused with a 400
@pytest.mark.parametrize(
	"value",
	["0", "0.00", "0.009", "-5", "5.001", "10000000000.00", "NaN", "Infinity", "1e999999", "abc", ""],
)
def test_refuses_amounts_outside_the_rule_with_a_400(value):
	with pytest.raises(BadRequest):
		_parse_amount(value)

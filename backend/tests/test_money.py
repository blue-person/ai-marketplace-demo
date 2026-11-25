# Import libraries
from decimal import Decimal
import pytest
from werkzeug.exceptions import BadRequest

# Import modules
from app.money import parse_usd, split_revenue

# Constants
MAX = Decimal("9999999999.99")


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
	assert parse_usd(value, MAX) == expected


# Amounts outside the rule are refused with a 400
@pytest.mark.parametrize(
	"value",
	["0", "0.00", "0.009", "-5", "5.001", "10000000000.00", "NaN", "Infinity", "1e999999", "abc", ""],
)
def test_refuses_amounts_outside_the_rule_with_a_400(value):
	with pytest.raises(BadRequest):
		parse_usd(value, MAX)


# The maximum and the label come from the caller so a price has its own limit and its own message
def test_the_maximum_and_the_label_come_from_the_caller():
	with pytest.raises(BadRequest) as error:
		parse_usd("1000.01", Decimal("1000.00"), "price")
	assert error.value.description == "The price must be between 0.01 and 1000.00 with at most two decimals."
	assert parse_usd("1000.00", Decimal("1000.00"), "price") == Decimal("1000.00")


# A text that is not a number names the label in the message
def test_a_text_that_is_not_a_number_names_the_label():
	with pytest.raises(BadRequest) as error:
		parse_usd("abc", Decimal("1000.00"), "price")
	assert error.value.description == "The price is not a valid number."


# The two shares add up to the exact price for every price of 0.01 to 1000.00 with no rounding
def test_the_shares_add_up_to_the_price_for_every_cent():
	for cents in range(1, 100001):
		price = Decimal(cents) / 100
		developer_share, platform_fee = split_revenue(price)
		assert developer_share + platform_fee == price
		assert developer_share == price * Decimal("0.8")
		assert platform_fee == price * Decimal("0.2")
		assert developer_share.as_tuple().exponent >= -4
		assert platform_fee.as_tuple().exponent >= -4


# The shares are Decimal values and a price of one cent keeps fractions of a cent
def test_the_shares_are_decimals_and_keep_fractions_of_a_cent():
	developer_share, platform_fee = split_revenue(Decimal("0.01"))
	assert (developer_share, platform_fee) == (Decimal("0.0080"), Decimal("0.0020"))
	assert isinstance(developer_share, Decimal)
	assert isinstance(platform_fee, Decimal)

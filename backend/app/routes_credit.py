# Import libraries
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, jsonify, request

# Import modules
from . import audit
from .db import query, retry_on_deadlock, transaction
from .rbac import RECEIVE_CREDIT, SEND_CREDIT, can, require
from .security import current_actor, current_user, find_target_by_email, login_required

# Blueprint of the credit routes
bp = Blueprint("credit", __name__, url_prefix="/api/credit")

# Constants
CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("9999999999.99")
HISTORY_LIMIT = 50


# Raised inside the transaction when the sender cannot pay so everything is undone
class NotEnoughBalanceError(Exception):
	pass


# Turn the amount of the request into a positive Decimal with at most two decimals
def _parse_amount(value) -> Decimal:
	try:
		amount = Decimal(str(value).strip())
	except InvalidOperation:
		abort(400, description="The amount is not a valid number.")

	# The checks run in this order because NaN cannot be compared and huge exponents cannot be rounded
	if not amount.is_finite() or not CENT <= amount <= MAX_AMOUNT or amount != amount.quantize(CENT):
		abort(400, description="The amount must be between 0.01 and 9999999999.99 with at most two decimals.")
	return amount


# Lock both accounts in the order of their ids so two crossed transfers cannot deadlock
def _lock_accounts(tx, first_id: int, second_id: int) -> list:
	return tx.query(
		"SELECT id, status FROM accounts WHERE id IN (%s, %s) ORDER BY id FOR UPDATE",
		(first_id, second_id),
	)


# Move credit between two accounts in one transaction and repeat it after a deadlock
@retry_on_deadlock
def _transfer(sender_id: int, recipient_id: int, amount: Decimal) -> int:
	with transaction() as tx:
		locked = _lock_accounts(tx, sender_id, recipient_id)
		if len(locked) != 2 or any(row["status"] != "active" for row in locked):
			abort(404, description="The recipient was not found.")

		# Charge the sender only when the balance is enough
		if not tx.execute(
			"UPDATE accounts SET balance = balance - %s WHERE id = %s AND balance >= %s",
			(amount, sender_id, amount),
		):
			raise NotEnoughBalanceError
		tx.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, recipient_id))

		# The transfer and its two ledger rows are saved in the same transaction
		transfer_id = tx.insert(
			"INSERT INTO transfers (from_account_id, to_account_id, amount) VALUES (%s, %s, %s)",
			(sender_id, recipient_id, amount),
		)
		tx.insert(
			"INSERT INTO ledger_entries (account_id, amount, entry_type, transfer_id) VALUES (%s, %s, 'transfer_out', %s)",
			(sender_id, -amount, transfer_id),
		)
		tx.insert(
			"INSERT INTO ledger_entries (account_id, amount, entry_type, transfer_id) VALUES (%s, %s, 'transfer_in', %s)",
			(recipient_id, amount, transfer_id),
		)
		audit.record(
			tx,
			"credit_transfer",
			"success",
			sender_id,
			recipient_id,
			details={"amount": amount, "transfer_id": transfer_id},
		)
		return transfer_id


# Return the balance and the latest ledger rows of the signed in account
@bp.get("")
@login_required
def credit():
	account_id = current_user()["id"]

	# Both reads share one snapshot so the balance matches the rows
	with transaction() as tx:
		account = tx.query("SELECT balance FROM accounts WHERE id = %s", (account_id,), one=True)
		entries = tx.query(
			"SELECT id, amount, entry_type, transfer_id, created_at FROM ledger_entries "
			"WHERE account_id = %s ORDER BY id DESC LIMIT %s",
			(account_id, HISTORY_LIMIT),
		)
	return jsonify(balance=account["balance"], entries=entries)


# Send credit to another active account found by its email
@bp.post("/transfers")
@login_required
def create_transfer():
	actor = current_actor()
	require(actor, SEND_CREDIT)
	data = request.get_json(silent=True) or {}
	recipient_email = str(data.get("recipient_email", "")).strip().lower()
	amount = _parse_amount(data.get("amount"))
	sender_id = actor.id

	# The recipient id and role never change, so they can be read before the transaction
	recipient = find_target_by_email(recipient_email)

	# An account that cannot receive credit looks like an account that does not exist
	if not recipient or not can(actor, RECEIVE_CREDIT, recipient):
		abort(404, description="The recipient was not found.")
	if recipient.id == sender_id:
		abort(400, description="You cannot transfer credit to yourself.")

	try:
		transfer_id = _transfer(sender_id, recipient.id, amount)
	except NotEnoughBalanceError:
		return jsonify(error="The balance is not enough."), 402
	balance = query("SELECT balance FROM accounts WHERE id = %s", (sender_id,), one=True)["balance"]
	return jsonify(transfer_id=transfer_id, balance=balance), 201


# List the transfers sent and received by the signed in account
@bp.get("/transfers")
@login_required
def list_transfers():
	account_id = current_user()["id"]
	transfers = query(
		"SELECT t.id, t.amount, t.created_at, sender.email AS from_email, recipient.email AS to_email "
		"FROM transfers t "
		"JOIN accounts sender ON sender.id = t.from_account_id "
		"JOIN accounts recipient ON recipient.id = t.to_account_id "
		"WHERE t.from_account_id = %s OR t.to_account_id = %s ORDER BY t.id DESC LIMIT %s",
		(account_id, account_id, HISTORY_LIMIT),
	)
	return jsonify(transfers=transfers)

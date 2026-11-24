# Import libraries
import secrets
from decimal import Decimal

# Import modules
from . import mail
from .api_keys import NewApiKey, new_api_key
from .countries import is_valid_country
from .db import query, retry_on_deadlock, transaction

# Constants
REFERRAL_BONUS = Decimal("5.00")
MAX_REFERRAL_BONUSES = 5
MAX_NAME_LENGTH = 120
MIN_ORGANIZATION_LENGTH = 2
MAX_ORGANIZATION_LENGTH = 100
REFERRAL_CODE_BYTES = 8
REJECTION_REASONS = {
	"incomplete_profile": "Incomplete profile",
	"duplicate_account": "Duplicate account",
	"unverifiable_information": "Unverifiable information",
	"other": "Other",
}


# True when the organization has a length that the profile accepts
def is_valid_organization(text: str) -> bool:
	return MIN_ORGANIZATION_LENGTH <= len(text.strip()) <= MAX_ORGANIZATION_LENGTH


# A profile is complete when the organization and the country are filled and valid
def is_profile_complete(account: dict) -> bool:
	organization = account.get("organization") or ""
	country = account.get("country") or ""
	return is_valid_organization(organization) and is_valid_country(country)


# Return the id of the active account that owns the referral code or None
def find_referrer_id(code: str) -> int | None:
	row = query("SELECT id FROM accounts WHERE referral_code = %s AND status = 'active'", (code,), one=True)
	return row["id"] if row else None


# List the pending accounts with the referrer and the result of the profile check
def pending_registrations() -> list[dict]:
	rows = query(
		"SELECT a.id, a.name, a.email, a.role, a.organization, a.country, a.created_at, "
		"r.email AS referrer_email "
		"FROM accounts a LEFT JOIN accounts r ON r.id = a.referred_by "
		"WHERE a.status = 'pending' ORDER BY a.id"
	)
	for row in rows:
		row["profile_complete"] = is_profile_complete(row)
	return rows


# List the pending accounts with only the profile fields the robot reads
def pending_profiles() -> list[dict]:
	return query("SELECT id, organization, country FROM accounts WHERE status = 'pending' ORDER BY id")


# Lock the accounts in the order of their ids so two transactions cannot deadlock
def _lock_accounts(tx, account_ids: list[int]) -> dict:
	ids = sorted(set(account_ids))

	# Only the placeholders are joined and the ids travel as parameters
	placeholders = ", ".join(["%s"] * len(ids))
	rows = tx.query(
		f"SELECT id, name, email, status FROM accounts WHERE id IN ({placeholders}) ORDER BY id FOR UPDATE",
		tuple(ids),
	)
	return {row["id"]: row for row in rows}


# Save the hash of the key and replace the previous one so only one key stays valid
def _store_api_key(tx, account_id: int, api_key: NewApiKey) -> None:
	tx.execute(
		"INSERT INTO api_keys (account_id, key_hash, key_prefix) VALUES (%s, %s, %s) AS new "
		"ON DUPLICATE KEY UPDATE key_hash = new.key_hash, key_prefix = new.key_prefix, created_at = CURRENT_TIMESTAMP",
		(account_id, api_key.key_hash, api_key.prefix),
	)


# Pay the bonus to an active referrer that has not reached the limit
def _pay_referral_bonus(tx, referrer: dict, referred_id: int) -> None:
	if referrer["status"] != "active":
		return

	# The referrer row is locked, so this count already includes every committed bonus
	paid = tx.query(
		"SELECT COUNT(*) AS total FROM ledger_entries WHERE account_id = %s AND entry_type = 'referral_bonus'",
		(referrer["id"],),
		one=True,
	)["total"]
	if paid >= MAX_REFERRAL_BONUSES:
		return
	tx.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (REFERRAL_BONUS, referrer["id"]))
	tx.insert(
		"INSERT INTO ledger_entries (account_id, amount, entry_type, referred_account_id) "
		"VALUES (%s, %s, 'referral_bonus', %s)",
		(referrer["id"], REFERRAL_BONUS, referred_id),
	)


# A repeated code breaks the unique key and the approval is rolled back
def _new_referral_code() -> str:
	return secrets.token_urlsafe(REFERRAL_CODE_BYTES)


# Activate the account, create its key and pay the bonus in one transaction
@retry_on_deadlock
def _approve(account_id: int, referrer_id: int | None, reviewer_id: int | None):
	with transaction() as tx:
		ids = [account_id] if referrer_id is None else [account_id, referrer_id]
		locked = _lock_accounts(tx, ids)

		# The condition on the status makes a second approval change nothing
		approved = tx.execute(
			"UPDATE accounts SET status = 'active', reviewed_at = NOW(), reviewed_by = %s, referral_code = %s "
			"WHERE id = %s AND status = 'pending'",
			(reviewer_id, _new_referral_code(), account_id),
		)
		if not approved:
			return None
		api_key = new_api_key()
		_store_api_key(tx, account_id, api_key)
		if referrer_id is not None:
			_pay_referral_bonus(tx, locked[referrer_id], account_id)
		return locked[account_id], api_key


# Approve a pending account and send its key after the commit
def approve_account(account_id: int, reviewer_id: int | None) -> bool:
	row = query("SELECT referred_by FROM accounts WHERE id = %s", (account_id,), one=True)
	if row is None:
		return False
	result = _approve(account_id, row["referred_by"], reviewer_id)
	if result is None:
		return False
	account, api_key = result

	# The account stays approved even when the email cannot be sent
	mail.send(
		account["email"],
		"Your account was approved",
		f"Hello {account['name']}. Your account is now active.\n\n"
		f"Your API key is {api_key.key}\n"
		"It is shown only once, and you can create a new one from your dashboard.",
	)
	return True


# Mark a pending account as rejected in one transaction
@retry_on_deadlock
def _reject(account_id: int, reviewer_id: int, reason: str):
	with transaction() as tx:
		rejected = tx.execute(
			"UPDATE accounts SET status = 'rejected', reviewed_at = NOW(), reviewed_by = %s, rejection_reason = %s "
			"WHERE id = %s AND status = 'pending'",
			(reviewer_id, reason, account_id),
		)
		if not rejected:
			return None
		return tx.query("SELECT name, email FROM accounts WHERE id = %s", (account_id,), one=True)


# Reject a pending account and send a generic email after the commit
def reject_account(account_id: int, reviewer_id: int, reason: str) -> bool:
	account = _reject(account_id, reviewer_id, reason)
	if account is None:
		return False
	mail.send(
		account["email"],
		"Your registration was not approved",
		f"Hello {account['name']}. Your registration request was not approved.",
	)
	return True


# Replace the key of an active account and return the new one or None
@retry_on_deadlock
def regenerate_api_key(account_id: int) -> NewApiKey | None:
	with transaction() as tx:
		locked = _lock_accounts(tx, [account_id])
		if locked.get(account_id, {}).get("status") != "active":
			return None
		api_key = new_api_key()
		_store_api_key(tx, account_id, api_key)
		return api_key

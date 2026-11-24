# Import modules
from . import audit
from .db import query, retry_on_deadlock, transaction
from .rbac import MANAGE_ACCOUNT_STATUS, AccountTarget, Actor, can

# Constants
STATUS_ACTIONS = {"active": "suspend", "suspended": "reactivate"}
STATUS_EVENTS = {"suspended": "account_suspended", "active": "account_reactivated"}


# Raised inside the transaction when the change would leave no active administrator
class LastAdminError(Exception):
	pass


# List the accounts with the status action that the actor may offer for each one
def list_accounts(actor: Actor) -> list[dict]:
	rows = query("SELECT id, name, email, role, status, organization, country, created_at FROM accounts ORDER BY id")
	accounts = []
	for row in rows:
		target = AccountTarget(row["id"], row["role"], row["status"], row["organization"], row["country"])
		action = STATUS_ACTIONS.get(row["status"])

		# Only the two active states can change and the policy decides who may change them
		allowed = action is not None and can(actor, MANAGE_ACCOUNT_STATUS, target)
		accounts.append(
			{
				"id": row["id"],
				"name": row["name"],
				"email": row["email"],
				"role": row["role"],
				"status": row["status"],
				"created_at": row["created_at"],
				"action": action if allowed else None,
			}
		)
	return accounts


# Lock the active administrators by id so two that suspend each other are served one at a time
def _keep_one_admin(tx, account_id: int) -> None:
	admins = tx.query("SELECT id FROM accounts WHERE role = 'admin' AND status = 'active' ORDER BY id FOR UPDATE")
	if account_id in {row["id"] for row in admins} and len(admins) <= 1:
		raise LastAdminError


# Change the status in one transaction and keep an active administrator
@retry_on_deadlock
def change_status(account_id: int, admin_id: int, from_status: str, to_status: str) -> bool:
	with transaction() as tx:
		if to_status == "suspended":
			_keep_one_admin(tx, account_id)

		# The condition on the current status makes a repeated request change nothing
		changed = tx.execute(
			"UPDATE accounts SET status = %s WHERE id = %s AND status = %s",
			(to_status, account_id, from_status),
		)
		if not changed:
			return False
		audit.record(
			tx,
			STATUS_EVENTS[to_status],
			"success",
			admin_id,
			account_id,
			details={"from": from_status, "to": to_status},
		)
		return True

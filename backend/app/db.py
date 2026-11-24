# Import libraries
from contextlib import contextmanager
import mysql.connector
from flask import current_app, g
from mysql.connector import errors
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

# Constants
DUPLICATE_ERRNO = 1062
DEADLOCK_ERRNO = 1213
MAX_ATTEMPTS = 3


# Raised when a write breaks a unique key
class DuplicateError(Exception):
	pass


# Open the connection on first use and reuse it within the same app context
def connection():
	if "db" not in g:
		g.db = mysql.connector.connect(**current_app.config["DB"], autocommit=True)
	return g.db


# Close the database connection at the end of the app context
def close(_exception=None):
	db = g.pop("db", None)
	if db is not None:
		db.close()


# Return rows as dictionaries so columns can be read by name
def _read(db, sql: str, params: tuple, one: bool):
	cursor = db.cursor(dictionary=True)

	# Release the cursor after the read even when it fails
	try:
		cursor.execute(sql, params)
		return cursor.fetchone() if one else cursor.fetchall()
	finally:
		cursor.close()


# Read outside a transaction and see the last committed data
def query(sql: str, params: tuple = (), one: bool = False):
	return _read(connection(), sql, params, one)


# Statements that run inside one open transaction
class Transaction:
	def __init__(self, db):
		self._db = db

	# Read inside the transaction and add FOR UPDATE to lock the rows
	def query(self, sql: str, params: tuple = (), one: bool = False):
		return _read(self._db, sql, params, one)

	# Run a write and return the number of rows it changed
	def execute(self, sql: str, params: tuple = ()) -> int:
		cursor = self._db.cursor()

		# Release the cursor after the write even when it fails
		try:
			cursor.execute(sql, params)
			return cursor.rowcount
		finally:
			cursor.close()

	# Run an insert and return the new row id
	def insert(self, sql: str, params: tuple = ()) -> int:
		cursor = self._db.cursor()

		# Release the cursor after the write even when it fails
		try:
			cursor.execute(sql, params)
			return cursor.lastrowid
		finally:
			cursor.close()


# Run the block as one transaction with a commit at the end and a rollback on any error
@contextmanager
def transaction():
	db = connection()
	db.start_transaction()
	try:
		yield Transaction(db)
		db.commit()

	# A repeated unique key becomes a neutral error for the routes
	except errors.IntegrityError as error:
		db.rollback()
		if error.errno == DUPLICATE_ERRNO:
			raise DuplicateError from error
		raise

	# Undo every change when anything else fails
	except BaseException:
		db.rollback()
		raise


# True when MySQL rolled the transaction back because of a deadlock
def _is_deadlock(error: BaseException) -> bool:
	return isinstance(error, errors.Error) and error.errno == DEADLOCK_ERRNO


# Run the whole decorated function again after a deadlock with a random growing wait
retry_on_deadlock = retry(
	retry=retry_if_exception(_is_deadlock),
	stop=stop_after_attempt(MAX_ATTEMPTS),
	wait=wait_random_exponential(multiplier=0.05, max=0.5),
	reraise=True,
)

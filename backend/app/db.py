"""Database access.

query("SELECT * FROM accounts WHERE id = %s", (account_id,), one=True)
execute("UPDATE accounts SET name = %s WHERE id = %s", (name, account_id))
commit()
"""

import mysql.connector
from flask import current_app, g


def connection():
	if "db" not in g:
		g.db = mysql.connector.connect(**current_app.config["DB"], autocommit=False)
	return g.db


def close(_exception=None):
	db = g.pop("db", None)
	if db is not None:
		db.close()


def query(sql: str, params: tuple = (), one: bool = False):
	cursor = connection().cursor(dictionary=True)
	try:
		cursor.execute(sql, params)
		return cursor.fetchone() if one else cursor.fetchall()
	finally:
		cursor.close()


def execute(sql: str, params: tuple = ()) -> int:
	"""Runs INSERT/UPDATE/DELETE. Returns the inserted id (if any)."""
	cursor = connection().cursor()
	try:
		cursor.execute(sql, params)
		return cursor.lastrowid
	finally:
		cursor.close()


def commit():
	connection().commit()

# Import libraries
import mysql.connector
from flask import current_app, g


# Open the connection on first use and reuse it within the same app context
def connection():
	if "db" not in g:
		g.db = mysql.connector.connect(**current_app.config["DB"], autocommit=False)
	return g.db


def close(_exception=None):
	db = g.pop("db", None)
	if db is not None:
		db.close()


# Return rows as dictionaries so columns can be read by name
def query(sql: str, params: tuple = (), one: bool = False):
	cursor = connection().cursor(dictionary=True)
	try:
		cursor.execute(sql, params)
		return cursor.fetchone() if one else cursor.fetchall()
	finally:
		cursor.close()


# Run a write statement and return the new row id when there is one
def execute(sql: str, params: tuple = ()) -> int:
	cursor = connection().cursor()
	try:
		cursor.execute(sql, params)
		return cursor.lastrowid
	finally:
		cursor.close()


def commit():
	connection().commit()

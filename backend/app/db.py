# Import libraries
import mysql.connector
from flask import current_app, g


# Open the connection on first use and reuse it within the same app context
def connection():
	if "db" not in g:
		g.db = mysql.connector.connect(**current_app.config["DB"], autocommit=False)
	return g.db


# Close the database connection at the end of the app context
def close(_exception=None):
	db = g.pop("db", None)
	if db is not None:
		db.close()


# Return rows as dictionaries so columns can be read by name
def query(sql: str, params: tuple = (), one: bool = False):
	cursor = connection().cursor(dictionary=True)

	# Release the cursor after the read even when it fails
	try:
		cursor.execute(sql, params)
		return cursor.fetchone() if one else cursor.fetchall()
	finally:
		cursor.close()


# Run a write statement and return the new row id when there is one
def execute(sql: str, params: tuple = ()) -> int:
	cursor = connection().cursor()

	# Release the cursor after the write even when it fails
	try:
		cursor.execute(sql, params)
		return cursor.lastrowid
	finally:
		cursor.close()


# Commit the open transaction on the current connection
def commit():
	connection().commit()

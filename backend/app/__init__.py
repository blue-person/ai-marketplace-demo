# Import libraries
import logging
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

# Import modules
from . import db, routes_admin, routes_auth, routes_credit, routes_general, routes_internal
from .config import load_config


# Create and configure the Flask application
def create_app() -> Flask:
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

	app = Flask(__name__)
	app.config.update(load_config())

	# Register the route blueprints
	app.register_blueprint(routes_general.bp)
	app.register_blueprint(routes_auth.bp)
	app.register_blueprint(routes_admin.bp)
	app.register_blueprint(routes_credit.bp)
	app.register_blueprint(routes_internal.bp)

	# Close the database connection when the request context ends
	app.teardown_appcontext(db.close)

	# Let the Vite dev server and other clients call the API
	@app.after_request
	def cors(response):
		origin = request.headers.get("Origin")
		if origin:
			response.headers["Access-Control-Allow-Origin"] = origin
			response.headers["Access-Control-Allow-Credentials"] = "true"
			response.headers["Access-Control-Allow-Headers"] = "Content-Type"
			response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
		return response

	# Return HTTP errors as JSON instead of HTML pages
	@app.errorhandler(HTTPException)
	def http_error(error):
		return jsonify(error=error.description or error.name), error.code

	# Log unexpected errors and hide the details from the client
	@app.errorhandler(Exception)
	def unexpected_error(error):
		app.logger.exception("Unhandled error")
		return jsonify(error="Internal server error."), 500

	return app

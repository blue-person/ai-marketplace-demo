# Import libraries
import hashlib
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, request

# Flask app singleton
app = Flask(__name__)

# Constants
MODELS = {
	"simulated/echo-1": {"name": "Echo 1 (simulated)", "prompt": "0.000001", "completion": "0.000002"},
	"simulated/summary-1": {"name": "Summary 1 (simulated)", "prompt": "0.000003", "completion": "0.000006"},
	"simulated/slow-1": {"name": "Slow 1 (simulated, takes 5 s)", "prompt": "0.000001", "completion": "0.000001"},
}

METRICS = {
	"heart-rate": ("heart_rate", "beats/min", 58, 105, 138),
	"step-count": ("step_count", "steps", 2000, 11000, 0),
	"oxygen-saturation": ("oxygen_saturation", "%", 94, 99, 86),
	"sleep-duration": ("sleep_duration", "h", 5, 9, 2),
}


# Build a JSON error response with its status code
def error(code: int, message: str):
	return jsonify(error={"code": code, "message": message}), code


# Every route except the health check requires a Bearer key
@app.before_request
def require_key():
	if request.path == "/health":
		return None
	header = request.headers.get("Authorization", "")

	# Require a non empty Bearer token in the Authorization header
	if not header.startswith("Bearer ") or len(header) <= len("Bearer "):
		return error(401, "Missing Authorization: Bearer <key> header.")
	return None


# Report that the service is running
@app.get("/health")
def health():
	return jsonify(status="ok")


# OpenRouter routes


# Return the simulated models with their prices
@app.get("/openrouter/api/v1/models")
def models():
	return jsonify(
		data=[
			{"id": key, "name": data["name"], "pricing": {"prompt": data["prompt"], "completion": data["completion"]}}
			for key, data in MODELS.items()
		]
	)


# Answer a chat request with a simulated completion
@app.post("/openrouter/api/v1/chat/completions")
def chat():
	body = request.get_json(silent=True) or {}
	model = body.get("model")
	messages = body.get("messages")
	if model not in MODELS:
		return error(400, f"Unknown model: {model!r}. See /models.")
	if not isinstance(messages, list) or not messages:
		return error(400, "'messages' must be a non-empty list.")

	# The slow model waits five seconds to mimic a long request
	if model == "simulated/slow-1":
		time.sleep(5)

	# Echo the last message cut to 200 characters
	last = str(messages[-1].get("content", "")) if isinstance(messages[-1], dict) else ""

	# Join the text of every message to estimate the input size
	input_text = " ".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
	content = f"[Simulated reply from {model}] I received: {last[:200]}"

	# Count words as a rough estimate of the token usage
	input_tokens = max(1, len(input_text.split()))
	output_tokens = len(content.split())

	# Build the response in the OpenAI chat completion format
	return jsonify(
		id=f"gen-sim-{uuid.uuid4()}",
		object="chat.completion",
		created=int(time.time()),
		model=model,
		choices=[{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
		usage={
			"prompt_tokens": input_tokens,
			"completion_tokens": output_tokens,
			"total_tokens": input_tokens + output_tokens,
		},
	)


# Open mHealth routes


# Return simulated Open mHealth data points for one metric
@app.get("/openmhealth/v1/dataPoints")
def data_points():
	schema = request.args.get("schema", "")
	user = request.args.get("user", "")

	# Read the days parameter and clamp it between 1 and 30
	try:
		days = min(max(int(request.args.get("days", "1")), 1), 30)
	except ValueError:
		return error(400, "'days' must be an integer between 1 and 30.")
	if schema not in METRICS:
		return error(400, f"Unsupported schema. Use one of: {', '.join(METRICS)}.")
	if not user or len(user) > 64:
		return error(400, "The 'user' parameter is required.")

	# Unpack the field name unit and limits of the metric
	field, unit, minimum, maximum, outlier = METRICS[schema]

	# Seed the random generator from the user and metric
	seed = int(hashlib.sha256(f"{user}:{schema}".encode()).hexdigest()[:16], 16)
	rng = random.Random(seed)

	# Heart rate and oxygen saturation are sampled hourly and the other metrics daily
	per_day = 24 if schema in ("heart-rate", "oxygen-saturation") else 1

	# Current UTC time truncated to the start of the hour
	now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

	# The shape follows Open mHealth without copying it exactly
	points = []

	# Build one data point for each sampling step back in time
	for i in range(days * per_day):
		moment = now - timedelta(hours=i) if per_day == 24 else now - timedelta(days=i)

		# Some values are out of range on purpose to test alerts
		value = outlier if rng.random() < 0.05 else rng.randint(minimum, maximum)

		# Add one data point in the Open mHealth layout
		points.append(
			{
				"header": {
					"id": str(uuid.UUID(int=rng.getrandbits(128))),
					"creation_date_time": moment.isoformat(),
					"schema_id": {"namespace": "omh", "name": schema, "version": "simulated"},
				},
				"body": {
					field: {"value": value, "unit": unit},
					"effective_time_frame": {"date_time": moment.isoformat()},
				},
			}
		)
	return jsonify(points)

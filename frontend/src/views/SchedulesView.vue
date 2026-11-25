<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api";

const MAX_PROMPT_LENGTH = 2000;
const UNITS = ["minutes", "hours", "days"];
const status_classes = { active: "text-bg-success", paused: "text-bg-warning", cancelled: "text-bg-secondary" };
const agents = ref([]);
const schedules = ref([]);
const limits = ref({});
const balance = ref("");
const error = ref("");
const list_error = ref("");
const saving = ref(false);
const form = ref(empty_form());

const selected = computed(() => agents.value.find((agent) => String(agent.id) === String(form.value.agent_id)));

// Return the values that a new form starts with
function empty_form() {
	return {
		agent_id: "",
		kind: "recurring",
		every: 1,
		unit: "hours",
		threshold_usd: "",
		cooldown_every: 1,
		cooldown_unit: "hours",
		prompt: "",
	};
}

// Show a date from the backend in the language of the browser
function format_time(text) {
	return new Date(text).toLocaleString();
}

// Show a number of seconds from the backend with the largest unit that divides it
function format_period(seconds) {
	if (seconds % 86400 === 0) return `${seconds / 86400} day(s)`;
	if (seconds % 3600 === 0) return `${seconds / 3600} hour(s)`;
	return `${seconds / 60} minute(s)`;
}

// Describe the rule of a schedule with the values that the backend stored
function describe_rule(item) {
	if (item.kind === "recurring") return `Every ${format_period(item.interval_seconds)}`;
	const threshold = Number.parseFloat(item.threshold_usd).toFixed(2);
	return `When the balance is above ${threshold} USD, at most once every ${format_period(item.cooldown_seconds)}`;
}

// Build the body of the request with only the fields of the chosen kind
function build_body() {
	const { agent_id, kind, prompt } = form.value;
	if (kind === "recurring") return { agent_id, kind, prompt, every: form.value.every, unit: form.value.unit };
	return {
		agent_id,
		kind,
		prompt,
		threshold_usd: form.value.threshold_usd,
		cooldown_every: form.value.cooldown_every,
		cooldown_unit: form.value.cooldown_unit,
	};
}

// Read the schedules and the limits again after every change
async function load() {
	list_error.value = "";
	try {
		const data = await api("/schedules");
		schedules.value = data.schedules;
		limits.value = data.limits;
		balance.value = data.balance;
	} catch (e) {
		list_error.value = e.message;
	}
}

// Send the form and leave every check to the backend
async function create() {
	error.value = "";
	saving.value = true;
	try {
		await api("/schedules", { method: "POST", body: build_body() });
		form.value = empty_form();
	} catch (e) {
		error.value = e.message;
	}
	saving.value = false;
	await load();
}

// Ask the backend to pause, resume or cancel a schedule
async function change(item, action) {
	list_error.value = "";
	try {
		await api(`/schedules/${item.id}/${action}`, { method: "POST" });
	} catch (e) {
		list_error.value = e.message;
	}
	await load();
}

onMounted(async () => {
	try {
		agents.value = (await api("/agents")).agents;
	} catch (e) {
		error.value = e.message;
	}
	await load();
});
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Scheduled executions</h1>
		<p>
			Balance: <strong>{{ balance }} USD</strong>
		</p>
		<p v-if="limits.max_open_schedules" class="text-muted small">
			You can have {{ limits.max_open_schedules }} schedules that are not cancelled. A recurring schedule runs
			every {{ limits.min_interval_minutes }} minutes or more and a conditional one waits at least
			{{ limits.min_cooldown_minutes }} minutes between launches. After
			{{ limits.max_failures_in_a_row }} failures in a row the schedule is paused.
		</p>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

		<form class="mb-4" @submit.prevent="create">
			<div class="mb-3">
				<label class="form-label" for="agent">Agent</label>
				<select id="agent" v-model="form.agent_id" class="form-select" required>
					<option value="" disabled>Select an agent</option>
					<option v-for="agent in agents" :key="agent.id" :value="agent.id">
						{{ agent.name }} ({{ agent.price_usd }} USD)
					</option>
				</select>
				<div v-if="selected" class="form-text">{{ selected.description }}</div>
			</div>
			<div class="mb-3">
				<label class="form-label" for="kind">Kind</label>
				<select id="kind" v-model="form.kind" class="form-select">
					<option value="recurring">Recurring, on a fixed interval</option>
					<option value="conditional">Conditional, when the balance is above a threshold</option>
				</select>
			</div>

			<div v-if="form.kind === 'recurring'" class="row g-2 mb-3">
				<div class="col-sm-3">
					<label class="form-label" for="every">Run every</label>
					<input id="every" v-model.number="form.every" type="number" min="1" class="form-control" required />
				</div>
				<div class="col-sm-3">
					<label class="form-label" for="unit">Unit</label>
					<select id="unit" v-model="form.unit" class="form-select">
						<option v-for="unit in UNITS" :key="unit" :value="unit">{{ unit }}</option>
					</select>
				</div>
			</div>
			<div v-else class="row g-2 mb-3">
				<div class="col-sm-4">
					<label class="form-label" for="threshold">Run when the balance is above (USD)</label>
					<input
						id="threshold"
						v-model="form.threshold_usd"
						inputmode="decimal"
						class="form-control"
						required
					/>
				</div>
				<div class="col-sm-3">
					<label class="form-label" for="cooldown_every">Wait at least</label>
					<input
						id="cooldown_every"
						v-model.number="form.cooldown_every"
						type="number"
						min="1"
						class="form-control"
						required
					/>
				</div>
				<div class="col-sm-3">
					<label class="form-label" for="cooldown_unit">Unit</label>
					<select id="cooldown_unit" v-model="form.cooldown_unit" class="form-select">
						<option v-for="unit in UNITS" :key="unit" :value="unit">{{ unit }}</option>
					</select>
				</div>
			</div>

			<div class="mb-3">
				<label class="form-label" for="prompt">Prompt</label>
				<textarea
					id="prompt"
					v-model="form.prompt"
					class="form-control"
					rows="3"
					:maxlength="MAX_PROMPT_LENGTH"
					required
				></textarea>
				<div class="form-text">{{ form.prompt.length }} of {{ MAX_PROMPT_LENGTH }} characters</div>
			</div>
			<button class="btn btn-dark" :disabled="saving">{{ saving ? "Saving" : "Schedule" }}</button>
		</form>

		<h2 class="h4 mb-3">My schedules</h2>
		<div v-if="list_error" class="alert alert-danger py-2">{{ list_error }}</div>
		<p v-if="!schedules.length">You have not scheduled any agent yet.</p>
		<table v-else class="table align-middle">
			<thead>
				<tr>
					<th>Agent</th>
					<th>Rule</th>
					<th>Status</th>
					<th>Next launch</th>
					<th>Last launch</th>
					<th>Prompt</th>
					<th></th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="item in schedules" :key="item.id" class="schedule-row">
					<td>{{ item.agent_name }}</td>
					<td class="small">{{ describe_rule(item) }}</td>
					<td>
						<span class="badge" :class="status_classes[item.status]">{{ item.status }}</span>
						<div v-if="item.pause_label" class="small text-muted">{{ item.pause_label }}</div>
					</td>
					<td class="small">{{ item.status === "active" ? format_time(item.next_run_at) : "" }}</td>
					<td class="small">
						<template v-if="item.last_run_at">
							{{ format_time(item.last_run_at) }}
							<div class="text-muted">{{ item.outcome_label }}</div>
							<RouterLink v-if="item.last_execution_id" to="/executions">See in my executions</RouterLink>
						</template>
						<div v-if="item.consecutive_failures" class="text-muted">
							{{ item.consecutive_failures }} failure(s) in a row
						</div>
					</td>
					<td class="small text-break">{{ item.prompt }}</td>
					<td class="text-nowrap">
						<button
							v-if="item.status === 'active'"
							class="btn btn-sm btn-outline-dark me-1"
							@click="change(item, 'pause')"
						>
							Pause
						</button>
						<button
							v-if="item.status === 'paused' && item.pause_reason !== 'admin'"
							class="btn btn-sm btn-outline-dark me-1"
							@click="change(item, 'resume')"
						>
							Resume
						</button>
						<button
							v-if="item.status !== 'cancelled'"
							class="btn btn-sm btn-outline-danger"
							@click="change(item, 'cancel')"
						>
							Cancel
						</button>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

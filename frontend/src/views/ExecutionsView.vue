<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/api";
import { session } from "@/session";

const MAX_PROMPT_LENGTH = 2000;
const route = useRoute();
const agents = ref([]);
const agent_id = ref("");
const prompt = ref("");
const balance = ref("");
const history = ref([]);
const earnings = ref([]);
const detail = ref(null);
const result = ref(null);
const error = ref("");
const history_error = ref("");
const running = ref(false);
const idempotency_key = ref(new_key());
const status_classes = { pending: "text-bg-warning", completed: "text-bg-success", failed: "text-bg-danger" };

const is_developer = computed(() => session.user && session.user.role === "developer");
const selected = computed(() => agents.value.find((agent) => String(agent.id) === String(agent_id.value)));

function new_key() {
	const bytes = crypto.getRandomValues(new Uint8Array(16));
	bytes[6] = (bytes[6] & 0x0f) | 0x40;
	bytes[8] = (bytes[8] & 0x3f) | 0x80;
	const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function format_time(text) {
	return new Date(text).toLocaleString();
}

async function load_history() {
	history_error.value = "";
	try {
		const data = await api("/executions");
		history.value = data.executions;
		balance.value = data.balance;
	} catch (e) {
		history_error.value = e.message;
	}
}

async function load_earnings() {
	try {
		earnings.value = (await api("/agents/mine/executions")).earnings;
	} catch (e) {
		history_error.value = e.message;
	}
}

async function run() {
	error.value = "";
	result.value = null;
	running.value = true;
	try {
		const data = await api(`/agents/${agent_id.value}/executions`, {
			method: "POST",
			body: { prompt: prompt.value },
			headers: { "Idempotency-Key": idempotency_key.value },
		});
		result.value = data.execution;
		balance.value = data.balance;
		prompt.value = "";
		idempotency_key.value = new_key();
	} catch (e) {
		error.value = e.message;
		if (e.status && e.status !== 409) idempotency_key.value = new_key();
	}
	running.value = false;
	await load_history();
	if (is_developer.value) await load_earnings();
}

async function show(execution) {
	try {
		detail.value = (await api(`/executions/${execution.id}`)).execution;
	} catch (e) {
		history_error.value = e.message;
	}
}

onMounted(async () => {
	try {
		agents.value = (await api("/agents")).agents;
		const wanted = route.query.agent;
		if (wanted && agents.value.some((agent) => String(agent.id) === String(wanted))) agent_id.value = wanted;
	} catch (e) {
		error.value = e.message;
	}
	await load_history();
	if (is_developer.value) await load_earnings();
});
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Run an agent</h1>
		<p>
			Balance: <strong>{{ balance }} USD</strong>
		</p>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

		<form class="mb-4" @submit.prevent="run">
			<div class="mb-3">
				<label class="form-label" for="agent">Agent</label>
				<select id="agent" v-model="agent_id" class="form-select" required>
					<option value="" disabled>Select an agent</option>
					<option v-for="agent in agents" :key="agent.id" :value="agent.id">
						{{ agent.name }} ({{ agent.price_usd }} USD)
					</option>
				</select>
				<div v-if="selected" class="form-text">{{ selected.description }}</div>
			</div>
			<div class="mb-3">
				<label class="form-label" for="prompt">Prompt</label>
				<textarea
					id="prompt"
					v-model="prompt"
					class="form-control"
					rows="4"
					:maxlength="MAX_PROMPT_LENGTH"
					required
				></textarea>
				<div class="form-text">{{ prompt.length }} of {{ MAX_PROMPT_LENGTH }} characters</div>
			</div>
			<button class="btn btn-dark" :disabled="running">{{ running ? "Running" : "Run" }}</button>
		</form>

		<div v-if="result" class="card mb-4">
			<div class="card-body">
				<h2 class="h5">Result of {{ result.agent_name }}</h2>
				<p class="mb-2 text-break" style="white-space: pre-wrap">{{ result.response }}</p>
				<div class="small text-muted">Cost {{ result.cost_usd }} USD</div>
			</div>
		</div>

		<h2 class="h4 mb-3">My executions</h2>
		<div v-if="history_error" class="alert alert-danger py-2">{{ history_error }}</div>
		<p v-if="!history.length">You have not run any agent yet.</p>
		<table v-else class="table align-middle">
			<thead>
				<tr>
					<th>Date</th>
					<th>Agent</th>
					<th>Cost</th>
					<th>Status</th>
					<th>Prompt</th>
					<th>Result</th>
					<th></th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="execution in history" :key="execution.id">
					<td class="small">{{ format_time(execution.created_at) }}</td>
					<td>{{ execution.agent_name }}</td>
					<td>{{ execution.cost_usd }} USD</td>
					<td>
						<span class="badge" :class="status_classes[execution.status]">{{ execution.status }}</span>
						<div v-if="execution.failure_label" class="small text-muted">{{ execution.failure_label }}</div>
					</td>
					<td class="small text-break">{{ execution.prompt_summary }}</td>
					<td class="small text-break">{{ execution.response_summary }}</td>
					<td>
						<button class="btn btn-sm btn-outline-dark" @click="show(execution)">View</button>
					</td>
				</tr>
			</tbody>
		</table>

		<div v-if="detail" class="card mb-4">
			<div class="card-body">
				<h2 class="h5">Execution {{ detail.id }} of {{ detail.agent_name }}</h2>
				<h3 class="h6">Prompt</h3>
				<p class="text-break" style="white-space: pre-wrap">{{ detail.prompt }}</p>
				<h3 class="h6">Result</h3>
				<p class="text-break" style="white-space: pre-wrap">{{ detail.response }}</p>
				<button class="btn btn-sm btn-outline-secondary" @click="detail = null">Close</button>
			</div>
		</div>

		<div v-if="is_developer">
			<h2 class="h4 mb-3">Earnings of my agents</h2>
			<p v-if="!earnings.length">Nobody has run your agents yet.</p>
			<table v-else class="table align-middle">
				<thead>
					<tr>
						<th>Date</th>
						<th>Agent</th>
						<th>Cost</th>
						<th>Status</th>
						<th>My share</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="item in earnings" :key="item.id">
						<td class="small">{{ format_time(item.created_at) }}</td>
						<td>{{ item.agent_name }}</td>
						<td>{{ item.cost_usd }} USD</td>
						<td>
							<span class="badge" :class="status_classes[item.status]">{{ item.status }}</span>
						</td>
						<td>{{ item.developer_share ? `${item.developer_share} USD` : "" }}</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

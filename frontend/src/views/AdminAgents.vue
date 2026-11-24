<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

const agents = ref([]);
const reasons = ref([]);
const loaded = ref(false);
const rejecting = ref(null);
const reason = ref("");
const message = ref("");
const error = ref("");

// The backend sends the list, so the page only shows it again after each action.
async function load() {
	try {
		const data = await api("/admin/agents");
		agents.value = data.agents;
		reasons.value = data.rejection_reasons;
	} catch (e) {
		error.value = e.message;
	}
	loaded.value = true;
}

async function run(agent, action, body) {
	message.value = "";
	error.value = "";
	try {
		message.value = (await api(`/admin/agents/${agent.id}/${action}`, { method: "POST", body })).message;
	} catch (e) {
		error.value = e.message;
	}
	await load();
}

function approve(agent) {
	if (confirm(`Approve ${agent.name}?`)) run(agent, "approve");
}

function open_reject(agent) {
	reason.value = "";
	rejecting.value = agent;
}

function cancel_reject() {
	rejecting.value = null;
}

async function confirm_reject() {
	const agent = rejecting.value;
	rejecting.value = null;
	await run(agent, "reject", { reason: reason.value });
}

onMounted(load);
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Agents to review</h1>
		<div v-if="message" class="alert alert-success py-2">{{ message }}</div>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
		<p v-if="loaded && !agents.length">There are no pending agents.</p>
		<table v-else-if="agents.length" class="table align-middle">
			<thead>
				<tr>
					<th>Name</th>
					<th>Developer</th>
					<th>Category</th>
					<th>Price</th>
					<th>Model</th>
					<th>Test endpoint</th>
					<th></th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="agent in agents" :key="agent.id">
					<td>
						<strong>{{ agent.name }}</strong>
						<div class="small text-muted">{{ agent.description }}</div>
					</td>
					<td>{{ agent.developer_email }}</td>
					<td>{{ agent.category }}</td>
					<td>{{ agent.price_usd }} USD</td>
					<td>{{ agent.model }}</td>
					<td class="small text-break">{{ agent.test_endpoint }}</td>
					<td class="d-flex gap-2">
						<button class="btn btn-dark btn-sm" @click="approve(agent)">Approve</button>
						<button class="btn btn-outline-danger btn-sm" @click="open_reject(agent)">Reject</button>
					</td>
				</tr>
			</tbody>
		</table>

		<div v-if="rejecting">
			<div class="modal d-block" tabindex="-1" role="dialog">
				<div class="modal-dialog modal-dialog-centered">
					<div class="modal-content">
						<div class="modal-header">
							<h2 class="modal-title h5">Reject {{ rejecting.name }}</h2>
						</div>
						<div class="modal-body">
							<label class="form-label" for="agent_reason">Please choose a reason from the list.</label>
							<select id="agent_reason" v-model="reason" class="form-select">
								<option value="">Select a reason</option>
								<option v-for="item in reasons" :key="item.key" :value="item.key">
									{{ item.label }}
								</option>
							</select>
						</div>
						<div class="modal-footer">
							<button class="btn btn-outline-secondary" @click="cancel_reject">Cancel</button>
							<button class="btn btn-danger" :disabled="!reason" @click="confirm_reject">Continue</button>
						</div>
					</div>
				</div>
			</div>
			<div class="modal-backdrop show"></div>
		</div>
	</div>
</template>

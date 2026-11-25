<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";
import AdminAgents from "@/views/AdminAgents.vue";
import AdminExecutions from "@/views/AdminExecutions.vue";

const registrations = ref([]);
const accounts = ref([]);
const action_labels = { suspend: "Suspend", reactivate: "Reactivate" };
const loaded = ref(false);
const reasons = ref([]);
const rejecting = ref(null);
const reason = ref("");
const message = ref("");
const error = ref("");
const tab = ref("requests");
const events = ref([]);
const categories = ref([]);
const category = ref("");
const account = ref("");
const next_before_id = ref(null);
const audit_error = ref("");
const category_labels = {
	authn: "Authentication",
	authz: "Authorization",
	registration: "Registration",
	account: "Account",
	credit: "Credit",
	agent: "Agent",
	execution: "Execution",
};

// The backend sends the list, so the page only shows it again after each action.
async function load() {
	try {
		const data = await api("/admin/registrations");
		registrations.value = data.registrations;
		reasons.value = data.rejection_reasons;
		accounts.value = (await api("/admin/accounts")).accounts;
	} catch (e) {
		error.value = e.message;
	}
	loaded.value = true;
}

async function run(path, body) {
	message.value = "";
	error.value = "";
	try {
		message.value = (await api(path, { method: "POST", body })).message;
	} catch (e) {
		error.value = e.message;
	}
	await load();
}

function decide(registration, action, body) {
	return run(`/admin/registrations/${registration.id}/${action}`, body);
}

function unlock(account) {
	if (confirm(`Unlock ${account.email}?`)) run(`/admin/accounts/${account.id}/unlock`);
}

function change_account(account) {
	if (confirm(`${action_labels[account.action]} ${account.email}?`)) {
		run(`/admin/accounts/${account.id}/${account.action}`);
	}
}

function approve(registration) {
	if (confirm(`Approve ${registration.email}?`)) decide(registration, "approve");
}

function open_reject(registration) {
	reason.value = "";
	rejecting.value = registration;
}

function cancel_reject() {
	rejecting.value = null;
}

async function confirm_reject() {
	const registration = rejecting.value;
	rejecting.value = null;
	await decide(registration, "reject", { reason: reason.value });
}

// The backend filters and pages the log, so the page only asks again and shows what arrives.
async function load_audit(older = false) {
	audit_error.value = "";
	const params = new URLSearchParams();
	if (category.value) params.set("category", category.value);
	if (account.value.trim()) params.set("account", account.value.trim());
	if (older) params.set("before_id", next_before_id.value);
	try {
		const data = await api(`/admin/audit?${params}`);
		events.value = older ? events.value.concat(data.events) : data.events;
		categories.value = data.categories;
		next_before_id.value = data.next_before_id;
	} catch (e) {
		audit_error.value = e.message;
	}
}

function open_audit() {
	tab.value = "audit";
	load_audit();
}

function pick_category(key) {
	category.value = key;
	load_audit();
}

function format_time(text) {
	return new Date(text).toLocaleString();
}

onMounted(load);
</script>

<template>
	<div>
		<ul class="nav nav-tabs mb-4">
			<li class="nav-item">
				<button class="nav-link" :class="{ active: tab === 'requests' }" @click="tab = 'requests'">
					Requests and accounts
				</button>
			</li>
			<li class="nav-item">
				<button class="nav-link" :class="{ active: tab === 'agents' }" @click="tab = 'agents'">Agents</button>
			</li>
			<li class="nav-item">
				<button class="nav-link" :class="{ active: tab === 'executions' }" @click="tab = 'executions'">
					Executions
				</button>
			</li>
			<li class="nav-item">
				<button class="nav-link" :class="{ active: tab === 'audit' }" @click="open_audit">Audit log</button>
			</li>
		</ul>

		<AdminAgents v-if="tab === 'agents'" />
		<AdminExecutions v-if="tab === 'executions'" />

		<div v-if="tab === 'audit'">
			<h1 class="h3 mb-3">Audit log</h1>
			<div v-if="audit_error" class="alert alert-danger py-2">{{ audit_error }}</div>
			<div class="d-flex flex-wrap gap-2 mb-3">
				<button
					class="btn btn-sm"
					:class="category === '' ? 'btn-dark' : 'btn-outline-dark'"
					@click="pick_category('')"
				>
					All
				</button>
				<button
					v-for="key in categories"
					:key="key"
					class="btn btn-sm"
					:class="category === key ? 'btn-dark' : 'btn-outline-dark'"
					@click="pick_category(key)"
				>
					{{ category_labels[key] || key }}
				</button>
			</div>
			<form class="d-flex gap-2 mb-3" @submit.prevent="load_audit()">
				<input
					v-model="account"
					class="form-control"
					type="text"
					maxlength="254"
					placeholder="Filter by account email"
					aria-label="Filter by account email"
				/>
				<button class="btn btn-outline-secondary" type="submit">Filter</button>
			</form>
			<p v-if="!events.length">There are no events for this filter.</p>
			<table v-else class="table table-sm align-middle">
				<thead>
					<tr>
						<th>When</th>
						<th>Event</th>
						<th>Result</th>
						<th>By</th>
						<th>On</th>
						<th>Details</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="event in events" :key="event.id">
						<td class="text-nowrap">{{ format_time(event.created_at) }}</td>
						<td>{{ event.action }}</td>
						<td>
							<span
								class="badge"
								:class="event.outcome === 'success' ? 'text-bg-success' : 'text-bg-danger'"
							>
								{{ event.outcome }}
							</span>
						</td>
						<td>{{ event.actor_email || "Anonymous" }}</td>
						<td>{{ event.target_email || event.target_label }}</td>
						<td class="small text-break">{{ event.details ? JSON.stringify(event.details) : "" }}</td>
					</tr>
				</tbody>
			</table>
			<button v-if="next_before_id" class="btn btn-outline-secondary" @click="load_audit(true)">Older</button>
		</div>

		<div v-if="tab === 'requests'">
			<h1 class="h3 mb-3">Registration requests</h1>
			<div v-if="message" class="alert alert-success py-2">{{ message }}</div>
			<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
			<p v-if="loaded && !registrations.length">There are no pending requests.</p>
			<table v-else-if="registrations.length" class="table align-middle">
				<thead>
					<tr>
						<th>Name</th>
						<th>Email</th>
						<th>Type</th>
						<th>Organization</th>
						<th>Country</th>
						<th>Referred by</th>
						<th>Profile</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="registration in registrations" :key="registration.id">
						<td>{{ registration.name }}</td>
						<td>{{ registration.email }}</td>
						<td>{{ registration.role }}</td>
						<td>{{ registration.organization }}</td>
						<td>{{ registration.country }}</td>
						<td>{{ registration.referrer_email }}</td>
						<td>{{ registration.profile_complete ? "Complete" : "Incomplete" }}</td>
						<td class="d-flex gap-2">
							<button class="btn btn-dark btn-sm" @click="approve(registration)">Approve</button>
							<button class="btn btn-outline-danger btn-sm" @click="open_reject(registration)">
								Reject
							</button>
						</td>
					</tr>
				</tbody>
			</table>

			<h2 class="h4 mt-5 mb-3">Accounts</h2>
			<table v-if="accounts.length" class="table align-middle">
				<thead>
					<tr>
						<th>Name</th>
						<th>Email</th>
						<th>Type</th>
						<th>Status</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="account in accounts" :key="account.id">
						<td>{{ account.name }}</td>
						<td>{{ account.email }}</td>
						<td>{{ account.role }}</td>
						<td>
							{{ account.status }}
							<span v-if="account.locked_until" class="badge text-bg-warning ms-1">
								Locked until {{ format_time(account.locked_until) }}
							</span>
						</td>
						<td>
							<button
								v-if="account.can_unlock"
								class="btn btn-outline-warning btn-sm me-1"
								@click="unlock(account)"
							>
								Unlock
							</button>
							<button
								v-if="account.action"
								class="btn btn-outline-secondary btn-sm"
								@click="change_account(account)"
							>
								{{ action_labels[account.action] }}
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-if="rejecting">
			<div class="modal d-block" tabindex="-1" role="dialog">
				<div class="modal-dialog modal-dialog-centered">
					<div class="modal-content">
						<div class="modal-header">
							<h2 class="modal-title h5">Reject {{ rejecting.email }}</h2>
						</div>
						<div class="modal-body">
							<label class="form-label" for="reason">Please choose a reason from the list.</label>
							<select id="reason" v-model="reason" class="form-select">
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

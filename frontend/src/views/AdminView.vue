<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

const registrations = ref([]);
const loaded = ref(false);
const reasons = ref([]);
const rejecting = ref(null);
const reason = ref("");
const message = ref("");
const error = ref("");

// The backend sends the list, so the page only shows it again after each action.
async function load() {
	try {
		const data = await api("/admin/registrations");
		registrations.value = data.registrations;
		reasons.value = data.rejection_reasons;
	} catch (e) {
		error.value = e.message;
	}
	loaded.value = true;
}

async function decide(registration, action, body) {
	message.value = "";
	error.value = "";
	try {
		message.value = (
			await api(`/admin/registrations/${registration.id}/${action}`, { method: "POST", body })
		).message;
	} catch (e) {
		error.value = e.message;
	}
	await load();
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

onMounted(load);
</script>

<template>
	<div>
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
						<button class="btn btn-outline-danger btn-sm" @click="open_reject(registration)">Reject</button>
					</td>
				</tr>
			</tbody>
		</table>

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

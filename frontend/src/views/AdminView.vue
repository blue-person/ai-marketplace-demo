<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

const registrations = ref([]);
const reasons = ref([]);
const chosen_reason = ref({});
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

function reject(registration) {
	const reason = chosen_reason.value[registration.id];
	if (!reason) {
		error.value = "Choose a reason before rejecting.";
		return;
	}
	if (confirm(`Reject ${registration.email}?`)) decide(registration, "reject", { reason });
}

onMounted(load);
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Registration requests</h1>
		<div v-if="message" class="alert alert-success py-2">{{ message }}</div>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
		<p v-if="!registrations.length">There are no pending requests.</p>
		<table v-else class="table align-middle">
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
						<select v-model="chosen_reason[registration.id]" class="form-select form-select-sm w-auto">
							<option :value="undefined">Reason</option>
							<option v-for="reason in reasons" :key="reason.key" :value="reason.key">
								{{ reason.label }}
							</option>
						</select>
						<button class="btn btn-outline-danger btn-sm" @click="reject(registration)">Reject</button>
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

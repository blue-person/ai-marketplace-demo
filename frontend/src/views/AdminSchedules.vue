<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

const status_classes = { active: "text-bg-success", paused: "text-bg-warning", cancelled: "text-bg-secondary" };
const schedules = ref([]);
const error = ref("");

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
	return `Balance above ${threshold} USD, every ${format_period(item.cooldown_seconds)} at most`;
}

// Read the schedules of everybody without their prompts
async function load() {
	error.value = "";
	try {
		schedules.value = (await api("/admin/schedules")).schedules;
	} catch (e) {
		error.value = e.message;
	}
}

// Ask the backend to pause, resume or cancel a schedule
async function change(item, action) {
	error.value = "";
	try {
		await api(`/admin/schedules/${item.id}/${action}`, { method: "POST" });
	} catch (e) {
		error.value = e.message;
	}
	await load();
}

onMounted(load);
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Schedules</h1>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
		<p v-if="!schedules.length">There are no schedules yet.</p>
		<table v-else class="table align-middle">
			<thead>
				<tr>
					<th>User</th>
					<th>Agent</th>
					<th>Rule</th>
					<th>Status</th>
					<th>Next launch</th>
					<th>Last launch</th>
					<th></th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="item in schedules" :key="item.id" class="admin-schedule-row">
					<td class="small">{{ item.user_email }}</td>
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
						</template>
						<div v-if="item.consecutive_failures" class="text-muted">
							{{ item.consecutive_failures }} failure(s) in a row
						</div>
					</td>
					<td class="text-nowrap">
						<button
							v-if="item.status === 'active'"
							class="btn btn-sm btn-outline-dark me-1"
							@click="change(item, 'pause')"
						>
							Pause
						</button>
						<button
							v-if="item.status === 'paused' && item.pause_reason === 'admin'"
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

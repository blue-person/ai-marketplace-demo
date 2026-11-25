<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

const executions = ref([]);
const platform_balance = ref("");
const error = ref("");
const status_classes = { pending: "text-bg-warning", completed: "text-bg-success", failed: "text-bg-danger" };

function format_time(text) {
	return new Date(text).toLocaleString();
}

onMounted(async () => {
	try {
		const data = await api("/admin/executions");
		executions.value = data.executions;
		platform_balance.value = data.platform_balance;
	} catch (e) {
		error.value = e.message;
	}
});
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Executions</h1>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
		<p>
			Platform balance: <strong>{{ platform_balance }} USD</strong>
		</p>
		<p v-if="!executions.length">There are no executions yet.</p>
		<table v-else class="table align-middle">
			<thead>
				<tr>
					<th>Date</th>
					<th>User</th>
					<th>Agent</th>
					<th>Status</th>
					<th>Cost</th>
					<th>Developer</th>
					<th>Platform</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="execution in executions" :key="execution.id">
					<td class="small">{{ format_time(execution.created_at) }}</td>
					<td class="small">{{ execution.user_email }}</td>
					<td>{{ execution.agent_name }}</td>
					<td>
						<span class="badge" :class="status_classes[execution.status]">{{ execution.status }}</span>
					</td>
					<td>{{ execution.cost_usd }} USD</td>
					<td>{{ execution.developer_share }}</td>
					<td>{{ execution.platform_fee }}</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

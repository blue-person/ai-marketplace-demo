<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

const balance = ref("");
const entries = ref([]);
const transfers = ref([]);
const recipient_email = ref("");
const amount = ref("");
const message = ref("");
const error = ref("");

async function load() {
	try {
		const credit = await api("/credit");
		balance.value = credit.balance;
		entries.value = credit.entries;
		transfers.value = (await api("/credit/transfers")).transfers;
	} catch (e) {
		error.value = e.message;
	}
}

async function send() {
	message.value = "";
	error.value = "";
	try {
		await api("/credit/transfers", {
			method: "POST",
			body: { recipient_email: recipient_email.value, amount: amount.value },
		});
		message.value = "Transfer completed.";
		recipient_email.value = "";
		amount.value = "";
		await load();
	} catch (e) {
		error.value = e.message;
	}
}

onMounted(load);
</script>

<template>
	<div class="col-lg-8">
		<h1 class="h3 mb-3">Credit</h1>
		<p class="fs-5">
			Balance: <strong>{{ balance }} USD</strong>
		</p>

		<h2 class="h5 mt-4">Transfer credit</h2>
		<form class="d-flex gap-2 mb-3" @submit.prevent="send">
			<input v-model="recipient_email" type="email" class="form-control" placeholder="Recipient email" required />
			<input v-model="amount" class="form-control" placeholder="Amount in USD" required />
			<button class="btn btn-dark">Send</button>
		</form>
		<div v-if="message" class="alert alert-success py-2">{{ message }}</div>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

		<h2 class="h5 mt-4">Transfers</h2>
		<ul class="list-group mb-4">
			<li v-for="transfer in transfers" :key="transfer.id" class="list-group-item d-flex justify-content-between">
				<span>{{ transfer.from_email }} to {{ transfer.to_email }}</span>
				<span>{{ transfer.amount }} USD</span>
			</li>
		</ul>

		<h2 class="h5">Ledger</h2>
		<ul class="list-group">
			<li v-for="entry in entries" :key="entry.id" class="list-group-item d-flex justify-content-between">
				<span>{{ entry.entry_type }}</span>
				<span>{{ entry.amount }} USD</span>
			</li>
		</ul>
	</div>
</template>

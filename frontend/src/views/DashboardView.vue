<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";
import { session } from "@/session";

const account = ref(null);
const name = ref("");
const message = ref("");
const result = ref(null);
const new_api_key = ref("");
const error = ref("");
let external_api_url = "";
let case_key = "";

onMounted(async () => {
	try {
		account.value = (await api(`/accounts/${session.user.id}`)).account;
		name.value = account.value.name;
		const config = await api("/config");
		external_api_url = config.external_api;
		case_key = config.case;
	} catch (e) {
		error.value = e.message;
	}
});

async function save_profile() {
	message.value = "";
	error.value = "";
	try {
		account.value = (
			await api(`/accounts/${session.user.id}`, { method: "PUT", body: { name: name.value } })
		).account;
		session.start({ ...session.user, name: account.value.name });
		message.value = "Profile updated.";
	} catch (e) {
		error.value = e.message;
	}
}

async function regenerate_key() {
	message.value = "";
	error.value = "";
	new_api_key.value = "";
	if (!confirm("The current key will stop working. Continue?")) return;
	try {
		const data = await api(`/accounts/${session.user.id}/api-key`, { method: "POST" });
		new_api_key.value = data.api_key;
		account.value.api_key_prefix = data.api_key_prefix;
	} catch (e) {
		error.value = e.message;
	}
}

async function test_external_api() {
	error.value = "";
	result.value = null;
	try {
		const path =
			case_key === "marketplace"
				? `/example/external-api?url=${encodeURIComponent(external_api_url + "/models")}`
				: "/example/external-api";
		result.value = await api(path);
	} catch (e) {
		error.value = e.message;
	}
}
</script>

<template>
	<div class="col-lg-8">
		<h1 class="h3">Dashboard</h1>
		<p v-if="account">
			Welcome, {{ account.name }}. Role: <strong>{{ account.role }}</strong>.
		</p>

		<h2 class="h5 mt-4">Referrals and API key</h2>
		<p v-if="account && account.referral_code">
			Your referral code: <code>{{ account.referral_code }}</code>
		</p>
		<p v-if="account && account.api_key_prefix">
			Current API key starts with <code>{{ account.api_key_prefix }}</code>
		</p>
		<button v-if="account && account.api_key_prefix" class="btn btn-outline-dark btn-sm" @click="regenerate_key">
			Create a new API key
		</button>
		<div v-if="new_api_key" class="alert alert-warning py-2 mt-3">
			Copy your new key now because it is shown only once: <code>{{ new_api_key }}</code>
		</div>

		<h2 class="h5 mt-4">My profile</h2>
		<form class="d-flex gap-2 mb-3" @submit.prevent="save_profile">
			<input v-model="name" class="form-control" />
			<button class="btn btn-dark">Save</button>
		</form>
		<div v-if="message" class="alert alert-success py-2">{{ message }}</div>

		<h2 class="h5 mt-4">External API</h2>
		<button class="btn btn-outline-dark btn-sm" @click="test_external_api">
			Test the external API (simulated)
		</button>
		<div v-if="error" class="alert alert-danger py-2 mt-3">{{ error }}</div>
		<pre v-if="result" class="bg-light border rounded p-3 mt-3 small">{{ JSON.stringify(result, null, 2) }}</pre>
	</div>
</template>

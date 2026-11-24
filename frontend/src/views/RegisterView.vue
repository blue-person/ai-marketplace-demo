<script setup>
import { onMounted, ref } from "vue";
import { api } from "@/api";

// The backend decides which account types and countries exist.
const roles = ref([]);
const countries = ref([]);
const form = ref({ name: "", email: "", password: "", role: "", organization: "", country: "", referral_code: "" });
const message = ref("");
const error = ref("");

onMounted(async () => {
	try {
		const config = await api("/config");
		roles.value = config.registration_roles;
		countries.value = config.countries;
		if (roles.value.length) form.value.role = roles.value[0].key;
	} catch (e) {
		error.value = e.message;
	}
});

async function register() {
	message.value = "";
	error.value = "";
	try {
		message.value = (await api("/auth/register", { method: "POST", body: form.value })).message;
		form.value.password = "";
	} catch (e) {
		error.value = e.message;
	}
}
</script>

<template>
	<div class="col-md-6">
		<h1 class="h3 mb-3">Sign up</h1>
		<form @submit.prevent="register">
			<div class="mb-3">
				<label class="form-label" for="name">Name</label>
				<input id="name" v-model="form.name" class="form-control" />
			</div>
			<div class="mb-3">
				<label class="form-label" for="email">Email</label>
				<input id="email" v-model="form.email" type="email" class="form-control" autocomplete="email" />
			</div>
			<div class="mb-3">
				<label class="form-label" for="password">Password</label>
				<input
					id="password"
					v-model="form.password"
					type="password"
					class="form-control"
					autocomplete="new-password"
				/>
			</div>
			<div class="mb-3">
				<label class="form-label" for="role">Account type</label>
				<select id="role" v-model="form.role" class="form-select">
					<option v-for="role in roles" :key="role.key" :value="role.key">{{ role.label }}</option>
				</select>
			</div>
			<div class="mb-3">
				<label class="form-label" for="organization">Organization (optional)</label>
				<input id="organization" v-model="form.organization" class="form-control" />
			</div>
			<div class="mb-3">
				<label class="form-label" for="country">Country (optional)</label>
				<select id="country" v-model="form.country" class="form-select">
					<option value="">Select a country</option>
					<option v-for="country in countries" :key="country.code" :value="country.code">
						{{ country.name }}
					</option>
				</select>
			</div>
			<div class="mb-3">
				<label class="form-label" for="referral_code">Referral code (optional)</label>
				<input id="referral_code" v-model="form.referral_code" class="form-control" autocomplete="off" />
			</div>
			<div v-if="message" class="alert alert-success py-2">{{ message }}</div>
			<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
			<button class="btn btn-dark">Sign up</button>
		</form>
	</div>
</template>

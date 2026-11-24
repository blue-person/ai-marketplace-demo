<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api";

const roles = ref({});
const form = ref({ name: "", email: "", password: "", role: "" });
const message = ref("");
const error = ref("");

// Only the publicly registrable roles are shown in the form.
const public_roles = computed(() =>
	Object.entries(roles.value)
		.filter(([, data]) => data.public_registration)
		.map(([key, data]) => ({ key, label: data.label })),
);

onMounted(async () => {
	try {
		roles.value = (await api("/config")).roles;
		if (public_roles.value.length) form.value.role = public_roles.value[0].key;
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
					<option v-for="role in public_roles" :key="role.key" :value="role.key">{{ role.label }}</option>
				</select>
			</div>
			<div v-if="message" class="alert alert-success py-2">{{ message }}</div>
			<div v-if="error" class="alert alert-danger py-2" v-html="error"></div>
			<button class="btn btn-dark">Sign up</button>
		</form>
	</div>
</template>

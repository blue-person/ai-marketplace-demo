<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api";
import { session } from "@/session";

const router = useRouter();
const email = ref("");
const password = ref("");
const error = ref("");

async function login() {
	error.value = "";
	try {
		const data = await api("/auth/login", {
			method: "POST",
			body: { email: email.value, password: password.value },
		});
		session.start(data.user);
		router.push({ name: "dashboard" });
	} catch (e) {
		error.value = e.message;
	}
}
</script>

<template>
	<div class="col-md-5">
		<h1 class="h3 mb-3">Sign in</h1>
		<form @submit.prevent="login">
			<div class="mb-3">
				<label class="form-label" for="email">Email</label>
				<input id="email" v-model="email" type="text" class="form-control" autocomplete="username" />
			</div>
			<div class="mb-3">
				<label class="form-label" for="password">Password</label>
				<input
					id="password"
					v-model="password"
					type="password"
					class="form-control"
					autocomplete="current-password"
				/>
			</div>
			<div v-if="error" class="alert alert-danger py-2" v-html="error"></div>
			<button class="btn btn-dark">Sign in</button>
		</form>
	</div>
</template>

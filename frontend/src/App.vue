<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { session } from "@/session";
import { api } from "@/api";

const router = useRouter();
const case_name = ref("Project");

onMounted(async () => {
	try {
		case_name.value = (await api("/config")).name;
	} catch {
		/* The backend is not responding yet; keep the generic name. */
	}
});

async function sign_out() {
	await session.sign_out();
	router.push({ name: "home" });
}
</script>

<template>
	<nav class="navbar navbar-expand navbar-dark bg-dark mb-4">
		<div class="container">
			<RouterLink class="navbar-brand" to="/">{{ case_name }}</RouterLink>
			<ul class="navbar-nav me-auto">
				<li class="nav-item">
					<RouterLink class="nav-link" to="/directory">Directory</RouterLink>
				</li>
				<li class="nav-item" v-if="session.user">
					<RouterLink class="nav-link" to="/dashboard">Dashboard</RouterLink>
				</li>
				<li class="nav-item" v-if="session.user">
					<RouterLink class="nav-link" to="/credit">Credit</RouterLink>
				</li>
				<li class="nav-item" v-if="session.user">
					<RouterLink class="nav-link" to="/agents">Agents</RouterLink>
				</li>
				<li class="nav-item" v-if="session.user && ['developer', 'company'].includes(session.user.role)">
					<RouterLink class="nav-link" to="/executions">Executions</RouterLink>
				</li>
				<li class="nav-item" v-if="session.user && ['developer', 'company'].includes(session.user.role)">
					<RouterLink class="nav-link" to="/schedules">Schedules</RouterLink>
				</li>
				<li class="nav-item" v-if="session.user && session.user.role === 'admin'">
					<RouterLink class="nav-link" to="/admin">Admin</RouterLink>
				</li>
			</ul>
			<div v-if="session.user" class="d-flex align-items-center gap-3 text-white">
				<span>{{ session.user.name }} ({{ session.user.role }})</span>
				<button class="btn btn-outline-light btn-sm" @click="sign_out">Sign out</button>
			</div>
			<div v-else class="d-flex gap-2">
				<RouterLink class="btn btn-outline-light btn-sm" to="/login">Sign in</RouterLink>
				<RouterLink class="btn btn-light btn-sm" to="/register">Sign up</RouterLink>
			</div>
		</div>
	</nav>
	<main class="container">
		<RouterView />
	</main>
</template>

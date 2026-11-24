<script setup>
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/api";

const route = useRoute();
const router = useRouter();
const term = ref(route.query.q || "");
const searched = ref("");
const results = ref([]);
const error = ref("");

async function search() {
	error.value = "";
	router.replace({ query: term.value ? { q: term.value } : {} });
	try {
		results.value = (await api(`/directory?q=${encodeURIComponent(term.value)}`)).results;
		searched.value = term.value;
	} catch (e) {
		error.value = e.message;
	}
}

onMounted(search);
</script>

<template>
	<div class="col-lg-8">
		<h1 class="h3 mb-3">Directory</h1>
		<form class="d-flex gap-2 mb-3" @submit.prevent="search">
			<input v-model="term" class="form-control" placeholder="Search by name" />
			<button class="btn btn-dark">Search</button>
		</form>
		<p v-if="searched" class="text-secondary" v-html="`Results for: <strong>${searched}</strong>`"></p>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
		<ul class="list-group">
			<li v-for="account in results" :key="account.id" class="list-group-item d-flex justify-content-between">
				<span v-html="account.name"></span>
				<span class="badge text-bg-secondary">{{ account.role }}</span>
			</li>
		</ul>
	</div>
</template>

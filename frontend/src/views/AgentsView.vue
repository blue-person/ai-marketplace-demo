<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "@/api";
import { session } from "@/session";

const agents = ref([]);
const categories = ref([]);
const category = ref("");
const error = ref("");
const own_agents = ref([]);
const models = ref([]);
const publish_error = ref("");
const publish_message = ref("");
const empty_form = { name: "", description: "", price_usd: "", category: "", test_endpoint: "", model: "" };
const form = ref({ ...empty_form });

// The role only decides what is shown, because the backend refuses the requests of other roles.
const is_developer = computed(() => session.user && session.user.role === "developer");
const status_classes = { pending: "text-bg-warning", approved: "text-bg-success", rejected: "text-bg-danger" };

function category_label(key) {
	const found = categories.value.find((item) => item.key === key);
	return found ? found.label : key;
}

async function load_catalog() {
	error.value = "";
	const params = category.value ? `?category=${encodeURIComponent(category.value)}` : "";
	try {
		const data = await api(`/agents${params}`);
		agents.value = data.agents;
		categories.value = data.categories;
	} catch (e) {
		error.value = e.message;
	}
}

function pick_category(key) {
	category.value = key;
	load_catalog();
}

async function load_own() {
	try {
		own_agents.value = (await api("/agents/mine")).agents;
		models.value = (await api("/agents/options")).models;
	} catch (e) {
		publish_error.value = e.message;
	}
}

async function publish() {
	publish_message.value = "";
	publish_error.value = "";
	try {
		const data = await api("/agents", { method: "POST", body: form.value });
		publish_message.value = data.message;
		form.value = { ...empty_form };
		own_agents.value = (await api("/agents/mine")).agents;
	} catch (e) {
		publish_error.value = e.message;
	}
}

onMounted(async () => {
	await load_catalog();
	if (is_developer.value) await load_own();
});
</script>

<template>
	<div>
		<h1 class="h3 mb-3">Agents</h1>
		<div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

		<div class="d-flex flex-wrap gap-2 mb-3">
			<button
				class="btn btn-sm"
				:class="category === '' ? 'btn-dark' : 'btn-outline-dark'"
				@click="pick_category('')"
			>
				All
			</button>
			<button
				v-for="item in categories"
				:key="item.key"
				class="btn btn-sm"
				:class="category === item.key ? 'btn-dark' : 'btn-outline-dark'"
				@click="pick_category(item.key)"
			>
				{{ item.label }}
			</button>
		</div>

		<p v-if="!agents.length && !error">There are no agents in this category yet.</p>
		<div class="row g-3 mb-5">
			<div v-for="agent in agents" :key="agent.id" class="col-md-6 col-lg-4">
				<div class="card h-100">
					<div class="card-body">
						<h2 class="h5 card-title">{{ agent.name }}</h2>
						<p class="card-text">{{ agent.description }}</p>
						<span class="badge text-bg-secondary me-1">{{ category_label(agent.category) }}</span>
						<span class="badge text-bg-light border">{{ agent.model }}</span>
					</div>
					<div class="card-footer d-flex justify-content-between small">
						<span>{{ agent.developer_name }}</span>
						<strong>{{ agent.price_usd }} USD</strong>
					</div>
				</div>
			</div>
		</div>

		<div v-if="is_developer">
			<h2 class="h4 mb-3">Publish an agent</h2>
			<p class="text-muted">A new agent stays pending until an administrator reviews it.</p>
			<div v-if="publish_message" class="alert alert-success py-2">{{ publish_message }}</div>
			<div v-if="publish_error" class="alert alert-danger py-2">{{ publish_error }}</div>
			<form class="row g-3 mb-5" @submit.prevent="publish">
				<div class="col-md-6">
					<label class="form-label" for="name">Name</label>
					<input id="name" v-model="form.name" class="form-control" maxlength="100" required />
				</div>
				<div class="col-md-6">
					<label class="form-label" for="price">Price per execution in USD</label>
					<input id="price" v-model="form.price_usd" class="form-control" placeholder="0.50" required />
				</div>
				<div class="col-12">
					<label class="form-label" for="description">Description</label>
					<textarea
						id="description"
						v-model="form.description"
						class="form-control"
						rows="3"
						maxlength="1000"
						required
					></textarea>
				</div>
				<div class="col-md-6">
					<label class="form-label" for="agent_category">Category</label>
					<select id="agent_category" v-model="form.category" class="form-select" required>
						<option value="" disabled>Select a category</option>
						<option v-for="item in categories" :key="item.key" :value="item.key">{{ item.label }}</option>
					</select>
				</div>
				<div class="col-md-6">
					<label class="form-label" for="model">Model</label>
					<select id="model" v-model="form.model" class="form-select" required>
						<option value="" disabled>Select a model</option>
						<option v-for="item in models" :key="item" :value="item">{{ item }}</option>
					</select>
				</div>
				<div class="col-12">
					<label class="form-label" for="test_endpoint">Test endpoint</label>
					<input
						id="test_endpoint"
						v-model="form.test_endpoint"
						class="form-control"
						maxlength="500"
						placeholder="https://my-agent.example.com/health"
						required
					/>
					<div class="form-text">The platform stores this address and never calls it.</div>
				</div>
				<div class="col-12">
					<button class="btn btn-dark">Publish</button>
				</div>
			</form>

			<h2 class="h4 mb-3">My agents</h2>
			<p v-if="!own_agents.length">You have not published any agent yet.</p>
			<table v-else class="table align-middle">
				<thead>
					<tr>
						<th>Name</th>
						<th>Category</th>
						<th>Price</th>
						<th>Test endpoint</th>
						<th>Status</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="agent in own_agents" :key="agent.id">
						<td>{{ agent.name }}</td>
						<td>{{ category_label(agent.category) }}</td>
						<td>{{ agent.price_usd }} USD</td>
						<td class="small text-break">{{ agent.test_endpoint }}</td>
						<td>
							<span class="badge" :class="status_classes[agent.status]">{{ agent.status }}</span>
							<div v-if="agent.rejection_label" class="small text-muted">{{ agent.rejection_label }}</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

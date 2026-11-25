import { createRouter, createWebHistory } from "vue-router";
import { session } from "@/session";
import HomeView from "@/views/HomeView.vue";
import LoginView from "@/views/LoginView.vue";
import RegisterView from "@/views/RegisterView.vue";
import DashboardView from "@/views/DashboardView.vue";
import DirectoryView from "@/views/DirectoryView.vue";
import CreditView from "@/views/CreditView.vue";
import AdminView from "@/views/AdminView.vue";
import AgentsView from "@/views/AgentsView.vue";
import ExecutionsView from "@/views/ExecutionsView.vue";
import SchedulesView from "@/views/SchedulesView.vue";

const router = createRouter({
	history: createWebHistory(),
	routes: [
		{ path: "/", name: "home", component: HomeView },
		{ path: "/login", name: "login", component: LoginView },
		{ path: "/register", name: "register", component: RegisterView },
		{ path: "/directory", name: "directory", component: DirectoryView },
		{ path: "/dashboard", name: "dashboard", component: DashboardView, meta: { requires_session: true } },
		{ path: "/credit", name: "credit", component: CreditView, meta: { requires_session: true } },
		{ path: "/agents", name: "agents", component: AgentsView, meta: { requires_session: true } },
		{
			path: "/executions",
			name: "executions",
			component: ExecutionsView,
			meta: { requires_session: true, roles: ["developer", "company"] },
		},
		{
			path: "/schedules",
			name: "schedules",
			component: SchedulesView,
			meta: { requires_session: true, roles: ["developer", "company"] },
		},
		// The role check here only saves a click, because the backend refuses the requests of other roles
		{ path: "/admin", name: "admin", component: AdminView, meta: { requires_session: true, roles: ["admin"] } },
	],
});

router.beforeEach((to) => {
	if (!to.meta.requires_session) return true;
	if (!session.is_active()) return { name: "login" };
	if (to.meta.roles && !to.meta.roles.includes(session.user.role)) return { name: "home" };
	return true;
});

export default router;

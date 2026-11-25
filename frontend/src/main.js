import "bootstrap/dist/css/bootstrap.min.css";
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import { hooks } from "./api";
import { session } from "./session";

hooks.unauthorized = () => {
	if (!session.user) return;
	session.forget();
	router.push({ name: "login", query: { expired: "1" } });
};

createApp(App).use(router).mount("#app");

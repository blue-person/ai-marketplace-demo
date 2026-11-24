// Session state in the browser. It is stored in localStorage so it
// survives a page reload.
import { reactive } from "vue";
import { api } from "./api";

function read_stored_user() {
  try {
    return JSON.parse(localStorage.getItem("user"));
  } catch {
    return null;
  }
}

export const session = reactive({
  user: read_stored_user(),

  start(user) {
    this.user = user;
    localStorage.setItem("user", JSON.stringify(user));
  },

  async sign_out() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    this.user = null;
    localStorage.removeItem("user");
  },

  is_active() {
    return document.cookie.includes("session=") && this.user !== null;
  },
});

// Minimal client for the backend. All routes are relative (/api/...).

export class ApiError extends Error {
	constructor(message, status) {
		super(message);
		this.status = status;
	}
}

export const hooks = { unauthorized: () => {} };

export async function api(path, { method = "GET", body, headers = {} } = {}) {
	const options = {
		method,
		credentials: "include",
		headers: { Accept: "application/json", ...headers },
	};
	if (method !== "GET") {
		options.headers["Content-Type"] = "application/json";
		options.headers["X-Requested-With"] = "fetch";
		options.body = JSON.stringify(body ?? {});
	}
	const response = await fetch(`/api${path}`, options);
	const data = await response.json().catch(() => ({}));
	if (response.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/logout")) {
		hooks.unauthorized();
	}
	if (!response.ok) {
		throw new ApiError(data.error || `Error ${response.status}`, response.status);
	}
	return data;
}

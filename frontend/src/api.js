// Minimal client for the backend. All routes are relative (/api/...).

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const options = {
    method,
    credentials: "include",
    headers: { Accept: "application/json" },
  };
  if (method !== "GET") {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body ?? {});
  }
  const response = await fetch(`/api${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(data.error || `Error ${response.status}`, response.status);
  }
  return data;
}

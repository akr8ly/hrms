function localApiBaseUrl() {
  // A SameSite session cookie is only sent when the frontend and API use the
  // same site. Keep `localhost` and `127.0.0.1` aligned during local work.
  const host = window.location.hostname === "localhost" ? "localhost" : "127.0.0.1";
  return `http://${host}:8000`;
}

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "" : localApiBaseUrl());

let sessionExpiryNotified = false;

export async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
    credentials: "include",
  });

  // Redis owns server-side sessions. A protected 401 means its session has
  // expired or was removed; an invalid login remains an inline login error.
  if (response.status === 401 && path !== "/auth/login" && path !== "/auth/register") {
    if (!sessionExpiryNotified) {
      sessionExpiryNotified = true;
      window.dispatchEvent(new CustomEvent("hrms:session-expired"));
    }
  }

  return response;
}

export function resetSessionExpiryNotification() {
  sessionExpiryNotified = false;
}

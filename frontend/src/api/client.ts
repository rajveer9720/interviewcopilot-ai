import axios from "axios";

const BASE_URL = import.meta.env.VITE_APP_API_URL || "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  withCredentials: true, // send the HttpOnly refresh_token cookie
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const stored = localStorage.getItem("interviewcopilot-store");
  if (stored) {
    try {
      const { state } = JSON.parse(stored);
      if (state?.accessToken && !config.headers.Authorization) {
        config.headers.Authorization = `Bearer ${state.accessToken}`;
      }
    } catch {}
  }
  return config;
});

function logoutAndRedirect() {
  localStorage.removeItem("interviewcopilot-store");
  window.location.href = ["file:", "app:"].includes(window.location.protocol) ? "#/login" : "/login";
}

// Dedupe concurrent 401s into a single in-flight refresh call.
let refreshPromise: Promise<string> | null = null;

export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post<{ access_token: string }>(`${BASE_URL}/auth/refresh`, {}, { withCredentials: true })
      .then(({ data }) => data.access_token)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// ── Response Interceptor: silently refresh on 401, else log out ──
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const isAuthEndpoint = original?.url?.includes("/auth/");

    if (error.response?.status === 401 && original && !original._retried && !isAuthEndpoint) {
      original._retried = true;
      try {
        const token = await refreshAccessToken();
        const { useStore } = await import("../store");
        useStore.getState().setAccessToken(token);
        original.headers.Authorization = `Bearer ${token}`;
        return apiClient(original);
      } catch {
        logoutAndRedirect();
        return Promise.reject(error);
      }
    }

    if (error.response?.status === 401) {
      logoutAndRedirect();
    }
    return Promise.reject(error);
  }
);

export function createSessionWebSocket(
  sessionId: string,
): WebSocket {
  const wsBase = BASE_URL.replace("http", "ws").replace("/api/v1", "");
  const url = `${wsBase}/ws/session/${sessionId}`;
  console.info("[InterviewCopilot][WS] connecting", { sessionId, wsBase });
  return new WebSocket(url);
}

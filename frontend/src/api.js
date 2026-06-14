// Thin fetch wrapper. Uses relative /api URLs (Vite proxies to the backend).
async function get(path) {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

// Owner-only admin token. Captured once from ?admin=... in the URL, then
// persisted in localStorage so only the owner's browser can refresh.
const ADMIN_KEY = "fifa_admin_token";

export function initAdminToken() {
  const params = new URLSearchParams(window.location.search);
  const t = params.get("admin");
  if (t) {
    localStorage.setItem(ADMIN_KEY, t);
    params.delete("admin");
    const qs = params.toString();
    window.history.replaceState(
      {}, "", window.location.pathname + (qs ? `?${qs}` : "")
    );
  }
}

export function getAdminToken() {
  return localStorage.getItem(ADMIN_KEY) || "";
}

export function isAdmin() {
  return !!getAdminToken();
}

export const api = {
  status: () => get("/status"),
  groups: () => get("/groups"),
  bracket: () => get("/bracket"),
  news: () => get("/news"),
  matches: (stage) => get(`/matches${stage ? `?stage=${stage}` : ""}`),
  teams: () => get("/teams"),
  team: (id) => get(`/teams/${id}`),
  refresh: async () => {
    const res = await fetch("/api/refresh", {
      method: "POST",
      headers: { "X-Admin-Token": getAdminToken() },
    });
    return res.json();
  },
};

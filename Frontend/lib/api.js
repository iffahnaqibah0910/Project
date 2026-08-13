// Browser calls same-origin /api/* (proxied by next.config.js rewrites).
// Direct backend URL is only used when NEXT_PUBLIC_API_BASE is set.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";
export const WS_BASE =
  process.env.NEXT_PUBLIC_WS_BASE || "ws://127.0.0.1:8000";

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed: ${path}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return res.json();
}

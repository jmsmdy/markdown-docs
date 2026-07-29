/**
 * frontend/lib/utils.js — Shared utilities for all web components and the app shell.
 *
 * Exported as plain ES module functions; no bundler required.
 */

// ── Debounce ──────────────────────────────────────────────────────────────────

/**
 * Returns a debounced version of fn that delays execution by `wait` ms.
 * Cancels any pending execution when called again within the wait window.
 *
 * @param {Function} fn
 * @param {number} wait - milliseconds
 * @returns {Function}
 */
export function debounce(fn, wait) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), wait);
  };
}


// ── HTML helpers ──────────────────────────────────────────────────────────────

/**
 * Escape a string for safe insertion into HTML text nodes.
 * @param {string} str
 * @returns {string}
 */
export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


// ── API client ────────────────────────────────────────────────────────────────

/**
 * Minimal fetch wrapper. Throws with a descriptive message on non-2xx responses.
 * Always sends/receives JSON.
 */
export const api = {
  _base: "",

  /** GET */
  async get(path, params = {}) {
    const url = new URL(this._base + path, location.origin);
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
    const resp = await fetch(url, {
      headers: { "Accept": "application/json" },
    });
    return _checkResponse(resp);
  },

  /** POST */
  async post(path, body = {}) {
    const resp = await fetch(this._base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body),
    });
    return _checkResponse(resp);
  },

  /** PUT */
  async put(path, body = {}) {
    const resp = await fetch(this._base + path, {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body),
    });
    return _checkResponse(resp);
  },

  /** DELETE */
  async delete(path) {
    const resp = await fetch(this._base + path, {
      method: "DELETE",
      headers: { "Accept": "application/json" },
    });
    return _checkResponse(resp);
  },
};

async function _checkResponse(resp) {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch { /* use statusText */ }
    throw new Error(`HTTP ${resp.status}: ${detail}`);
  }
  // 204 No Content
  if (resp.status === 204) return null;
  return resp.json();
}


// ── Branch utilities ──────────────────────────────────────────────────────────

/**
 * Sanitise a user-supplied branch name fragment:
 * - lowercase
 * - replace spaces and illegal chars with hyphens
 * - trim leading/trailing hyphens
 *
 * @param {string} name
 * @returns {string}
 */
export function sanitizeBranchName(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9._/-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}


// ── URL / routing helpers ─────────────────────────────────────────────────────

/**
 * Build a URL for a document with optional branch and mode.
 * @param {string} path - doc path
 * @param {string} [branch]
 * @param {string} [mode] - "edit" | "view" | "diff"
 * @returns {string}
 */
export function docUrl(path, branch, mode) {
  const params = new URLSearchParams();
  if (branch) params.set("branch", branch);
  if (mode)   params.set("mode", mode);
  const qs = params.toString();
  return `/doc/${encodeURIComponent(path)}${qs ? "?" + qs : ""}`;
}

/**
 * Parse the current location into { path, branch, mode }.
 * @returns {{ path: string|null, branch: string|null, mode: string }}
 */
export function parseLocation() {
  const params = new URLSearchParams(location.search);
  const pathMatch = location.pathname.match(/^\/doc\/(.+)/);
  return {
    path: pathMatch ? decodeURIComponent(pathMatch[1]) : null,
    branch: params.get("branch"),
    mode: params.get("mode") || "edit",
  };
}


// ── Misc ──────────────────────────────────────────────────────────────────────

/**
 * Format a git commit date (ISO8601 string) to a human-readable relative time.
 * @param {string} isoDate
 * @returns {string}
 */
export function relativeTime(isoDate) {
  if (!isoDate) return "";
  const now = Date.now();
  const then = new Date(isoDate).getTime();
  const diff = Math.floor((now - then) / 1000);

  if (diff < 60)     return "just now";
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(isoDate).toLocaleDateString();
}

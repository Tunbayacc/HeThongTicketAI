// Fetch wrapper with an in-memory access token + single-flight 401 refresh.
// The access token never leaves JS memory; the refresh token is an HttpOnly
// cookie managed by the browser (design spec 6.1, SRS NFR-SEC-05).

let accessToken = null;
let refreshInFlight = null;

export function setAccessToken(token) {
  accessToken = token;
}

function toError(res, body) {
  const err = new Error(body?.message || `HTTP ${res.status}`);
  err.status = res.status;
  err.error_code = body?.error_code ?? null;
  err.details = body?.details ?? null;
  return err;
}

async function rawFetch(path, options = {}, withAuth = true) {
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (withAuth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw toError(res, body);
  return body;
}

// Never auto-refresh on the auth endpoints themselves (login failures and a
// failed refresh must surface as-is, not retry in a loop).
const NO_AUTO_REFRESH = new Set(['/api/auth/login', '/api/auth/refresh', '/api/auth/logout']);

async function request(path, options = {}) {
  try {
    return await rawFetch(path, options, true);
  } catch (err) {
    const canRefresh = !NO_AUTO_REFRESH.has(path) && err.status === 401;
    if (!canRefresh) throw err;
    if (!refreshInFlight) {
      refreshInFlight = rawFetch('/api/auth/refresh', { method: 'POST' }, false)
        .then((body) => {
          accessToken = body.access_token;
          return true;
        })
        .catch(() => {
          accessToken = null;
          return false;
        })
        .finally(() => {
          refreshInFlight = null;
        });
    }
    const refreshed = await refreshInFlight;
    if (!refreshed) throw err; // session really ended -> caller handles 401
    return rawFetch(path, options, true);
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
};

export { request };

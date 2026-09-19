// Session tokens live only in an HttpOnly cookie. Browser state is display data.
let auth = null;
try { localStorage.removeItem('landguard:auth'); } catch { /* Storage may be blocked. */ }
export function getAuth() { return auth; }
export function getUser() { return auth?.user || null; }
export function setAuth(value) {
  auth = value;
  window.dispatchEvent(new Event('landguard:auth-changed'));
}
export function clearAuth() { setAuth(null); }

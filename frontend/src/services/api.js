import { clearAuth } from './auth';
const base = `${import.meta.env.VITE_API_URL || ''}/api/v1`;
const identityCodes = new Set(['AUTH_NOT_CONFIGURED','IDENTITY_UNAVAILABLE','IDENTITY_REJECTED','INVALID_LOGIN','ACCOUNT_NOT_ACTIVE','SESSION_EXPIRED','RATE_LIMITED','MAIL_NOT_CONFIGURED','INVITATION_DELIVERY_FAILED','ACCOUNT_EXISTS','NOT_PENDING','INVITATION_INVALID','ADMIN_PROTECTED','NOT_ACTIVATED']);

export async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(`${base}${path}`, {
      ...options, credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-LandGuard-Request': '1', ...options.headers },
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('We cannot connect to the service. Check your connection and try again.');
  }
  if (!response.ok) {
    const messages = {
      404: 'This record could not be found or is outside your assigned scope.',
      409: 'This record conflicts with an existing account or project.',
      422: 'Check the required fields and assigned scope. Passwords for new accounts need at least 12 characters.',
      401: 'Sign in with your email and password to continue.',
      403: 'This action is not available with your current access.',
    };
    const body = await response.json().catch(() => ({}));
    if (response.status === 401) { clearAuth(); window.dispatchEvent(new Event('landguard:auth-required')); }
    const error = new Error(identityCodes.has(body.code) ? body.detail : messages[response.status] || 'The service is temporarily unavailable. Please try again.');
    error.status = response.status;
    error.code = body.code;
    throw error;
  }
  if (options.method && options.method !== 'GET' && !path.startsWith('/auth/')) window.dispatchEvent(new Event('landguard:data-changed'));
  if (response.status === 204) return null;
  try { return await response.json(); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('We could not read the response. Please try again.');
  }
}

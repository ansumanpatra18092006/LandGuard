# Connect real LandGuard accounts

The application has no demo login or default administrator password. Enrollment is invitation-only.

## 1. Create the identity tables

In **your Supabase project → SQL Editor**, paste and run all of [001_identity.sql](001_identity.sql).
This creates:

- `auth.users` is already managed by Supabase Auth: verified email and password hash.
- `public.landguard_profiles`: role, active/invited/disabled status, state, district and assigned project IDs.
- `public.landguard_sessions`: hashes of opaque application session tokens and expiration times.
- `public.landguard_auth_limits`: shared login/invitation rate counters.
- `public.landguard_auth_audit`: invitation, activation, sign-in and account-status events.

The four LandGuard tables have RLS enabled and privileges revoked from browser roles.
Only the backend service key may access them. Do not add public read/write policies.
Roles come from protected profiles, never from user-editable Supabase metadata.
Do not manually insert a plaintext password, or an independently hashed password, into any table.

## 2. Configure Supabase Auth

In Authentication settings:

1. Keep the Email/password provider enabled and email confirmation enabled.
2. Turn **Allow new users to sign up** off. The backend admin API provisions invitations.
3. Set the minimum password length to **12**. LandGuard also enforces 12–128 characters on activation.
4. Set Email OTP expiration to **3600 seconds** (or a shorter period required by your organization).
5. Set Site URL to your website origin. Include your website's `/accept-invitation` address in the redirect allowlist.
6. Do not manually create the initial admin in Authentication → Users. Use the bootstrap command below so the role profile and invitation are created together.

The code uses Supabase's admin **generate_link** endpoint and sends that link through Brevo; it does not use Supabase's built-in invitation email sender.
If you already manually created the intended admin email in Supabase, do not delete real accounts to retry. Use a new administrator email or have the deployment owner review and provision that existing identity explicitly.

## 3. Configure Brevo and the backend

Verify a sender email/domain in Brevo and obtain a transactional-email API key.
Create `C:\LandGuard\backend\.env` from [the example](../.env.example) if it does not exist; preserve existing database settings.

Fill these variables locally:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SUPABASE_SECRET_OR_SERVICE_ROLE_KEY
BREVO_API_KEY=YOUR_BREVO_API_KEY
BREVO_SENDER_EMAIL=YOUR_VERIFIED_SENDER_EMAIL
BREVO_SENDER_NAME=LandGuard AI
PUBLIC_APP_URL=http://127.0.0.1:5173
FRONTEND_ORIGIN=http://127.0.0.1:5173
SESSION_MINUTES=120
```

Use a Supabase `sb_secret_...` key or the legacy `service_role` key, **not** a publishable/anon key.
Never put these secrets in frontend code, `VITE_*` variables, Git, screenshots, email, or a source ZIP.
The root `.env` configures Docker; Python explicitly reads `backend/.env`.

For users on other computers, deploy the frontend and backend behind **one HTTPS origin**,
route `/api/` to FastAPI, and set both URL variables to that origin.
Localhost email links work only on the computer running LandGuard. Use the exact configured hostname consistently.
The frontend development proxy already forwards `/api` to port 8000.
Leave `VITE_API_URL` unset for this same-origin deployment.
Configure the proxy to preserve cookies and trust forwarded client IPs only from your own proxy; the application never directly trusts arbitrary forwarded headers.
Restart the backend after editing environment variables.

Brevo accepting an email does not guarantee delivery. Check Brevo transactional logs and the recipient's spam folder if it is missing.
Avoid analytics/click-tracking on activation links and do not record invitation URLs in application logs.

## 4. Invite the first real administrator

From PowerShell, replace the example email/name with your own real details:

```powershell
Set-Location C:\LandGuard\backend
..\.venv\Scripts\python.exe -m app.db.bootstrap_admin --email "your-real-email@your-organization.org" --name "Your Name"
```

This operator-only command sends a Brevo invitation; there is no public bootstrap endpoint.
The SQL function locks initial provisioning so concurrent attempts cannot create multiple first admins.
Open the received invitation, choose your password, then sign in at `/login`.

**Admin credentials are your invited email and the password you choose. There is no shared/default password.**
Supabase hashes the password in `auth.users`; the associated profile has `role = SYSTEM_ADMIN`.

If the first invitation failed or expired:

```powershell
..\.venv\Scripts\python.exe -m app.db.bootstrap_admin --email "your-real-email@your-organization.org" --name "Your Name" --resend
```

Do not rerun initial bootstrap to create more admins after one exists. The existing admin can invite additional administrators in the portal.

## 5. Add users in the portal

1. Sign in as the activated administrator.
2. Open **Users & invitations** in the sidebar (`/admin/users`).
3. Enter the colleague's name, work email and approved role.
4. Assign an exact state name for state officers; state and district for district officers; comma-separated project IDs for implementing agencies.
5. Select **Send invitation**. The user opens the email, sets a password and signs in.
6. Pending accounts can be resent invitations. Activated non-admin accounts can be disabled/enabled; disabling revokes their application sessions.

State/district names are matched exactly against project records. Review spelling and casing before inviting.
System administrators manage user access and authentication activity only; they do not receive project, GIS, analytics, alert, or AI access. Operational roles are scoped by state, district, or assigned project IDs. Project deletion is restricted to state officers within their state scope.
The same scope applies to dashboard aggregates, analytics, maps, notices and predictions.
Users cannot change their own roles or account assignments.
Administrator suspension is reserved for the deployment owner: set its profile status to `disabled` and delete its sessions using trusted Supabase administration, after ensuring another active administrator exists.

## Verification and current limits

Run backend tests with `..\.venv\Scripts\python.exe -m pytest -q` from `backend`, and `npm run build` from `frontend`.
`frontend/identity-smoke.cjs` checks UI flows with isolated browser API fixtures; it sends no email.
Provider-contract tests mock Supabase and Brevo; passing them is **not** proof that your cloud keys, SQL, sender or email delivery work.

After configuration, perform this live acceptance check with real authorized recipients:
bootstrap admin → accept once → sign in → invite one colleague → accept → verify assigned records →
disable colleague → confirm their session is rejected → sign out. A reused/expired invitation must fail.

This change moves **identity**, not existing project records, to Supabase. Project records continue using `DATABASE_URL` or local SQLite.
MFA, departmental SSO, self-service password recovery, editing existing assignments and invitation cancellation are not implemented.
For a lost active-account password, use the deployment owner's trusted Supabase account recovery process.
Expired application sessions are denied; periodically delete expired rows from `landguard_sessions` as housekeeping.

Official references: [Supabase user data](https://supabase.com/docs/guides/auth/managing-user-data),
[admin link generation](https://supabase.com/docs/reference/javascript/auth-admin-generatelink),
[Auth configuration](https://supabase.com/docs/guides/auth/general-configuration),
[password security](https://supabase.com/docs/guides/auth/password-security),
[Brevo transactional email](https://developers.brevo.com/reference/send-transac-email).

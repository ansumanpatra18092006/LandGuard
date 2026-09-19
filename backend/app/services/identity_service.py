"""Supabase Auth + protected profiles/sessions; Brevo only transports invitations."""
import hashlib
import html
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class IdentityError(Exception):
    def __init__(self, code: str, message: str, status: int = 503):
        self.code, self.message, self.status = code, message, status


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class IdentityService:
    def request(self, method, path, *, data=None, params=None, token=None):
        key = settings.supabase_service_role_key.get_secret_value()
        if not settings.supabase_url or not key:
            raise IdentityError("AUTH_NOT_CONFIGURED", "Supabase authentication is not configured.")
        headers = {"apikey": key, "Content-Type": "application/json", "Prefer": "return=representation"}
        if token:
            headers["Authorization"] = "Bearer " + token
        elif key.startswith("eyJ"):
            headers["Authorization"] = "Bearer " + key
        try:
            with httpx.Client(timeout=20) as client:
                response = client.request(method, settings.supabase_url.rstrip("/") + path,
                                          headers=headers, json=data, params=params)
        except httpx.HTTPError:
            raise IdentityError("IDENTITY_UNAVAILABLE", "The identity service is unavailable. Try again.") from None
        if response.is_error:
            if response.status_code == 429:
                raise IdentityError("RATE_LIMITED", "Too many attempts. Wait before trying again.", 429)
            if response.status_code in (400, 401, 403, 404, 409, 422):
                raise IdentityError("IDENTITY_REJECTED", "The identity service could not complete this request.", 400)
            raise IdentityError("IDENTITY_UNAVAILABLE", "The identity service is unavailable. Check its configuration.")
        if not response.content:
            return None
        return response.json()

    def table(self, name, method="GET", *, data=None, **params):
        return self.request(method, "/rest/v1/landguard_" + name, data=data, params=params)

    def rate_limit(self, subject, limit=10):
        bucket = token_digest(subject + ":" + str(int(time.time()) // 60))
        allowed = self.request("POST", "/rest/v1/rpc/landguard_auth_rate_limit",
                               data={"p_bucket": bucket, "p_limit": limit})
        if not allowed:
            raise IdentityError("RATE_LIMITED", "Too many attempts. Wait a minute before trying again.", 429)

    def profile(self, user_id):
        rows = self.table("profiles", id="eq." + str(user_id), limit="1")
        return rows[0] if rows else None

    def profile_by_email(self, email):
        rows = self.table("profiles", email="eq." + email, limit="1")
        return rows[0] if rows else None

    def audit(self, actor, subject, event):
        self.table("auth_audit", "POST", data={"actor_id": actor, "subject_id": subject, "event": event})

    def login(self, email, password):
        try:
            result = self.request("POST", "/auth/v1/token", params={"grant_type": "password"},
                                  data={"email": email, "password": password})
        except IdentityError as exc:
            if exc.code == "IDENTITY_REJECTED":
                raise IdentityError("INVALID_LOGIN", "Email or password is incorrect.", 401) from None
            raise
        user = result.get("user", {})
        profile = self.profile(user.get("id", ""))
        if not user.get("email_confirmed_at") or not profile or profile["status"] != "active":
            raise IdentityError("ACCOUNT_NOT_ACTIVE", "This account is not active. Contact your administrator.", 403)
        return profile

    def create_session(self, profile):
        token = secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc) + timedelta(minutes=settings.session_minutes)
        self.table("sessions", "POST", data={"token_hash": token_digest(token),
                   "user_id": profile["id"], "expires_at": expires.isoformat()})
        self.audit(profile["id"], profile["id"], "session_created")
        return token

    def session_user(self, token):
        rows = self.table("sessions", token_hash="eq." + token_digest(token), limit="1")
        if not rows or datetime.fromisoformat(rows[0]["expires_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
            raise IdentityError("SESSION_EXPIRED", "Sign in to continue.", 401)
        profile = self.profile(rows[0]["user_id"])
        if not profile or profile["status"] != "active":
            raise IdentityError("ACCOUNT_NOT_ACTIVE", "This account is not active.", 401)
        return profile

    def logout(self, token):
        self.table("sessions", "DELETE", token_hash="eq." + token_digest(token))

    def require_mail(self):
        if not settings.brevo_api_key.get_secret_value() or not settings.brevo_sender_email:
            raise IdentityError("MAIL_NOT_CONFIGURED", "Configure the Brevo API key and verified sender first.")

    def generate_invitation(self, email, *, recovery=False):
        result = self.request("POST", "/auth/v1/admin/generate_link",
                              data={"type": "recovery" if recovery else "invite", "email": email})
        # GoTrue REST returns user fields and link properties at the top level.
        user = result.get("user", result)
        properties = result.get("properties", result)
        return user, properties

    def send_invitation(self, profile, properties):
        fragment = urlencode({"token_hash": properties["hashed_token"],
                              "type": properties["verification_type"]})
        url = settings.public_app_url.rstrip("/") + "/accept-invitation#" + fragment
        body = {
            "sender": {"email": settings.brevo_sender_email, "name": settings.brevo_sender_name},
            "to": [{"email": profile["email"], "name": profile["display_name"]}],
            "subject": "Your invitation to LandGuard AI",
            "htmlContent": "<p>Hello " + html.escape(profile["display_name"]) + ",</p>"
                "<p>Your administrator has invited you to LandGuard AI as "
                + html.escape(profile["role"].replace("_", " ")) + ".</p>"
                '<p><a href="' + html.escape(url, quote=True) + '">Accept invitation and set your password</a></p>'
                "<p>This single-use link expires according to the project's Supabase email-link expiry setting. "
                "If it has expired, ask your administrator to resend it.</p>"
                "<p>If you were not expecting this invitation, you can ignore it.</p>",
        }
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post("https://api.brevo.com/v3/smtp/email", json=body,
                    headers={"api-key": settings.brevo_api_key.get_secret_value(), "accept": "application/json"})
            if response.status_code != 201:
                raise ValueError("Mail rejected")
        except (httpx.HTTPError, ValueError):
            self.table("profiles", "PATCH", id="eq." + profile["id"], data={"invitation_delivery": "failed"})
            raise IdentityError("INVITATION_DELIVERY_FAILED",
                "Account saved, but the invitation email was not confirmed. Use Resend invitation.", 502) from None
        self.table("profiles", "PATCH", id="eq." + profile["id"],
                   data={"invitation_delivery": "accepted_by_brevo", "invited_at": datetime.now(timezone.utc).isoformat()})

    def invite(self, payload, actor):
        self.require_mail()
        email = payload["email"]
        if self.profile_by_email(email):
            raise IdentityError("ACCOUNT_EXISTS", "An account already exists. Use Resend invitation for pending accounts.", 409)
        user, properties = self.generate_invitation(email)
        profile = {"id": user["id"], **payload, "status": "invited", "invited_by": actor["id"]}
        self.table("profiles", "POST", data=profile)
        self.audit(actor["id"], profile["id"], "user_invited")
        self.send_invitation(profile, properties)
        return self.profile(profile["id"])

    def resend(self, user_id, actor):
        self.require_mail()
        profile = self.profile(user_id)
        if not profile or profile["status"] != "invited":
            raise IdentityError("NOT_PENDING", "Only pending invitations can be resent.", 409)
        user = self.request("GET", "/auth/v1/admin/users/" + user_id)
        _, properties = self.generate_invitation(profile["email"], recovery=bool(user.get("email_confirmed_at")))
        self.send_invitation(profile, properties)
        self.audit(actor["id"], user_id, "invitation_resent")
        return self.profile(user_id)

    def accept(self, token_hash, kind, password):
        try:
            result = self.request("POST", "/auth/v1/verify", data={"token_hash": token_hash, "type": kind})
        except IdentityError as exc:
            if exc.code == "IDENTITY_REJECTED":
                raise IdentityError("INVITATION_INVALID", "This invitation is expired or already used. Ask your administrator to resend it.", 400) from None
            raise
        profile = self.profile(result["user"]["id"])
        if not profile or profile["status"] != "invited":
            raise IdentityError("INVITATION_INVALID", "This account has no pending invitation.", 403)
        # A verified invitation can only set the password for its own Supabase user.
        self.request("PUT", "/auth/v1/user", token=result["access_token"], data={"password": password})
        rows = self.table("profiles", "PATCH", id="eq." + profile["id"], status="eq.invited", data={"status": "active"})
        if not rows:
            raise IdentityError("INVITATION_INVALID", "The account can no longer be activated.", 409)
        self.audit(profile["id"], profile["id"], "invitation_accepted")
        return rows[0]

    def set_status(self, user_id, status, actor):
        profile = self.profile(user_id)
        if not profile or profile["role"] == "SYSTEM_ADMIN":
            raise IdentityError("ADMIN_PROTECTED", "System administrator accounts must be managed by the deployment owner.", 403)
        if profile["status"] == "invited":
            raise IdentityError("NOT_ACTIVATED", "An invitation must be accepted before the account can be enabled.", 409)
        rows = self.table("profiles", "PATCH", id="eq." + user_id, data={"status": status})
        self.table("sessions", "DELETE", user_id="eq." + user_id)
        self.audit(actor["id"], user_id, "account_" + status)
        return rows[0]


def get_identity_service():
    return IdentityService()

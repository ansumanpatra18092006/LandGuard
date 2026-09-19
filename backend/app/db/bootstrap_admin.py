"""Operator-only first-system-admin provisioning; sends a Brevo invitation, never a default password."""
import argparse

from app.schemas.auth import EmailRequest
from app.services.identity_service import IdentityError, IdentityService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--resend", action="store_true", help="Resend a pending first-system-admin invitation")
    args = parser.parse_args()
    email = EmailRequest(email=args.email).email
    name = args.name.strip()
    if len(name) < 2 or len(name) > 100:
        print("Enter a valid administrator name.")
        return 1
    service = IdentityService()
    try:
        service.require_mail()
        if args.resend:
            profile = service.profile_by_email(email)
            if not profile or profile["role"] != "SYSTEM_ADMIN":
                raise IdentityError("NOT_PENDING", "No matching system-administrator invitation exists.")
            service.resend(profile["id"], profile)
        else:
            existing = service.table("profiles", role="eq.SYSTEM_ADMIN", limit="1")
            if existing:
                raise IdentityError("ADMIN_EXISTS", "A system administrator is already provisioned. Use --resend if still pending.")
            user, properties = service.generate_invitation(email)
            service.request("POST", "/rest/v1/rpc/landguard_bootstrap_admin",
                data={"p_id": user["id"], "p_email": email, "p_name": name})
            profile = service.profile(user["id"])
            service.send_invitation(profile, properties)
        print("System-administrator invitation accepted by Brevo. Check the recipient inbox; delivery is not yet confirmed.")
    except IdentityError as exc:
        print(exc.message)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

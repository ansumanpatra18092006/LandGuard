from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response
from app.core.config import settings
from app.core.security import SESSION_COOKIE, current_user, require_roles
from app.schemas.auth import AuditEvent, AuthUser, LoginRequest, SessionResponse, SessionProbeResponse, InvitationRequest, InvitationAcceptRequest, ManagedUser, UserStatusRequest
from app.services.identity_service import IdentityError, IdentityService, get_identity_service

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/login", response_model=SessionResponse)
def login(payload: LoginRequest, request: Request, response: Response, identity: IdentityService = Depends(get_identity_service)):
    identity.rate_limit("login:" + (request.client.host if request.client else "unknown"))
    identity.rate_limit("email:" + payload.email)
    profile = identity.login(payload.email, payload.password)
    old = request.cookies.get(SESSION_COOKIE)
    if old:
        identity.logout(old)
    token = identity.create_session(profile)
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_minutes * 60,
                        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/api/v1")
    return {"user": profile}

@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, identity: IdentityService = Depends(get_identity_service)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        identity.logout(token)
    response.delete_cookie(SESSION_COOKIE, path="/api/v1", secure=settings.cookie_secure, httponly=True, samesite="lax")

@router.get("/session", response_model=SessionProbeResponse)
def session_probe(request: Request, response: Response, identity: IdentityService = Depends(get_identity_service)):
    """Return session state without using 401 for an anonymous browser.

    `/auth/me` intentionally remains protected and still returns 401 when a caller
    explicitly asks for an authenticated identity without a valid session. The
    frontend uses this probe on startup/focus so a normal signed-out state does
    not appear as a failed request in DevTools.
    """
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token or len(token) > 128:
        return {"authenticated": False, "user": None}
    try:
        user = identity.session_user(token)
    except IdentityError as exc:
        if exc.status == 401:
            response.delete_cookie(SESSION_COOKIE, path="/api/v1", secure=settings.cookie_secure, httponly=True, samesite="lax")
            return {"authenticated": False, "user": None}
        raise
    return {"authenticated": True, "user": user}


@router.get("/me", response_model=AuthUser)
def me(user=Depends(current_user)):
    return user

@router.post("/accept-invitation", response_model=AuthUser)
def accept_invitation(payload: InvitationAcceptRequest, request: Request, identity: IdentityService = Depends(get_identity_service)):
    identity.rate_limit("accept:" + (request.client.host if request.client else "unknown"))
    return identity.accept(payload.token_hash, payload.type, payload.password)

@router.get("/users", response_model=list[ManagedUser])
def users(_admin=Depends(require_roles("SYSTEM_ADMIN")), identity: IdentityService = Depends(get_identity_service)):
    return identity.table("profiles", order="created_at.desc", limit="1000")

@router.get("/audit", response_model=list[AuditEvent])
def audit(_admin=Depends(require_roles("SYSTEM_ADMIN")), identity: IdentityService = Depends(get_identity_service)):
    return identity.table("auth_audit", order="created_at.desc", limit="100")

@router.post("/invitations", response_model=ManagedUser, status_code=201)
def invite(payload: InvitationRequest, admin=Depends(require_roles("SYSTEM_ADMIN")), identity: IdentityService = Depends(get_identity_service)):
    identity.rate_limit("invite:" + str(admin["id"]), 5)
    return identity.invite(payload.model_dump(), admin)

@router.post("/users/{user_id}/resend", response_model=ManagedUser)
def resend(user_id: UUID, admin=Depends(require_roles("SYSTEM_ADMIN")), identity: IdentityService = Depends(get_identity_service)):
    identity.rate_limit("invite:" + str(admin["id"]), 5)
    return identity.resend(str(user_id), admin)

@router.patch("/users/{user_id}", response_model=ManagedUser)
def user_status(user_id: UUID, payload: UserStatusRequest, admin=Depends(require_roles("SYSTEM_ADMIN")), identity: IdentityService = Depends(get_identity_service)):
    return identity.set_status(str(user_id), payload.status, admin)

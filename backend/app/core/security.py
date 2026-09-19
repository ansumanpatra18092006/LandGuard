from fastapi import Depends, HTTPException, Request
from app.services.identity_service import IdentityService, get_identity_service

SESSION_COOKIE = "landguard_session"

def current_user(request: Request, identity: IdentityService = Depends(get_identity_service)):
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token or len(token) > 128:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    return identity.session_user(token)

def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dependency

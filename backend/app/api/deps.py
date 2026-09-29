from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.core.security import decode_token
bearer=HTTPBearer(auto_error=False)
def current_user(credentials: HTTPAuthorizationCredentials=Depends(bearer), db: Session=Depends(get_db)):
    payload=decode_token(credentials.credentials) if credentials else None
    user=db.get(User,int(payload["sub"])) if payload and payload.get("sub","").isdigit() else None
    if not user or not user.is_active: raise HTTPException(401,"Authentication required")
    return user
def roles(*allowed):
    def check(user: User=Depends(current_user)):
        if user.role not in allowed: raise HTTPException(403,"Your role cannot perform this action")
        return user
    return check

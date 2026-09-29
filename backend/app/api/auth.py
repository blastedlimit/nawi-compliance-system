from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User, AuditLog
from app.api.deps import current_user
from app.core.security import verify_password, create_token
router=APIRouter(prefix="/api/auth",tags=["auth"])
@router.post("/login")
def login(form: OAuth2PasswordRequestForm=Depends(),db:Session=Depends(get_db)):
    u=db.query(User).filter(User.email==form.username.lower()).first()
    if not u or not u.is_active or not verify_password(form.password,u.password_hash): raise HTTPException(401,"Email or password is incorrect")
    db.add(AuditLog(user_id=u.id,action="LOGIN",entity_type="USER",entity_id=str(u.id)));db.commit()
    return {"access_token":create_token(u.id),"token_type":"bearer","user":{"id":u.id,"name":u.name,"email":u.email,"role":u.role}}
@router.get("/me")
def me(u:User=Depends(current_user)): return {"id":u.id,"name":u.name,"email":u.email,"role":u.role}

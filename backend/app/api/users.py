from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User,AuditLog
from app.api.deps import roles
from app.core.security import hash_password
router=APIRouter(prefix="/api/users",tags=["users"])
ROLES={"ADMIN","LAB_TECHNICIAN","APPROVING_OFFICER"}
def output(x):return {"id":x.id,"name":x.name,"email":x.email,"role":x.role,"is_active":x.is_active,"created_at":x.created_at}
@router.get("")
def listing(db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    return [output(x) for x in db.query(User).order_by(User.name).all()]
@router.post("",status_code=201)
def create(d:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    name=str(d.get("name","")).strip();email=str(d.get("email","")).strip().lower();password=str(d.get("password",""));role=d.get("role")
    if not name or not email or not password:raise HTTPException(422,"Name, email and password are required")
    if len(password)<12:raise HTTPException(422,"New user passwords must be at least 12 characters")
    if role not in ROLES:raise HTTPException(422,"Choose a supported role")
    if db.query(User).filter_by(email=email).first():raise HTTPException(409,"Email is already registered")
    item=User(name=name,email=email,password_hash=hash_password(password),role=role,is_active=True)
    db.add(item);db.flush();db.add(AuditLog(user_id=u.id,action="USER_CREATED",entity_type="USER",entity_id=str(item.id),details=f"Role: {role}"));db.commit();db.refresh(item);return output(item)
@router.patch("/{user_id}")
def update(user_id:int,d:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    target=db.get(User,user_id)
    if not target:raise HTTPException(404,"User not found")
    if not d or set(d)-{"name","role","is_active"}:raise HTTPException(422,"Only name, role and active status may be updated")
    if target.id==u.id and (d.get("role",target.role)!="ADMIN" or d.get("is_active",target.is_active) is False):raise HTTPException(409,"You cannot remove your own administrator access")
    new_role=d.get("role",target.role);active=d.get("is_active",target.is_active)
    if new_role not in ROLES or not isinstance(active,bool):raise HTTPException(422,"Role or active status is invalid")
    if target.role=="ADMIN" and target.is_active and (new_role!="ADMIN" or active is False):
        count=db.query(User).filter(User.role=="ADMIN",User.is_active.is_(True)).count()
        if count<2:raise HTTPException(409,"The last active administrator cannot be deactivated or demoted")
    previous=f"name={target.name}; role={target.role}; active={target.is_active}"
    target.name=str(d.get("name",target.name)).strip();target.role=new_role;target.is_active=active
    if not target.name:raise HTTPException(422,"Name cannot be empty")
    db.add(AuditLog(user_id=u.id,action="USER_UPDATED",entity_type="USER",entity_id=str(target.id),details=previous+f" => name={target.name}; role={target.role}; active={target.is_active}"));db.commit();db.refresh(target);return output(target)
@router.get("/audit")
def audit(db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    return [{"id":a.id,"user":a.user_id,"action":a.action,"entity_type":a.entity_type,"entity_id":a.entity_id,"timestamp":a.timestamp,"details":a.details} for a in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200)]

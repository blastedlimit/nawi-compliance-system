from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Instrument, AuditLog, User, TestSession, ComplianceResult, Report, Attachment
from app.api.deps import current_user, roles
from app.compliance.validation import validate_instrument
router=APIRouter(prefix="/api/instruments",tags=["instruments"])
def output(x): return {k:getattr(x,k) for k in ("id","manufacturer","model","serial_number","instrument_type","accuracy_class","capacity_unit","max_capacity","min_capacity","verification_interval_e","display_interval_d","number_of_verification_intervals_n","created_at")}
@router.get("")
def list_items(q:str="",db:Session=Depends(get_db),u:User=Depends(current_user)):
    query=db.query(Instrument)
    if q: query=query.filter((Instrument.serial_number.contains(q))|(Instrument.model.contains(q))|(Instrument.manufacturer.contains(q)))
    return [output(x) for x in query.order_by(Instrument.created_at.desc()).all()]
@router.post("",status_code=201)
def create(data:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    errors=validate_instrument(data)
    if errors: raise HTTPException(422,detail={"message":"Please correct the instrument details.","errors":errors})
    if db.query(Instrument).filter_by(serial_number=data["serial_number"]).first(): raise HTTPException(409,"Serial number is already registered")
    x=Instrument(**{k:data[k] for k in ("manufacturer","model","serial_number","instrument_type","accuracy_class","capacity_unit","max_capacity","min_capacity","verification_interval_e","display_interval_d")},number_of_verification_intervals_n=round(float(data["max_capacity"])/float(data["verification_interval_e"])))
    db.add(x);db.flush();db.add(AuditLog(user_id=u.id,action="INSTRUMENT_CREATED",entity_type="INSTRUMENT",entity_id=str(x.id)));db.commit();db.refresh(x);return output(x)
@router.get("/{item_id}")
def detail(item_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    x=db.get(Instrument,item_id)
    if not x: raise HTTPException(404,"Instrument not found")
    result=output(x)
    result["test_history"]=[{"id":t.id,"test_date":str(t.test_date),"status":t.status,"operator":t.operator.name} for t in sorted(x.sessions,key=lambda y:y.created_at,reverse=True)]
    result["compliance_history"]=[{"test_session_id":t.id,"test_type":r.test_type,"status":r.status,"calculated_value":r.calculated_value,"calculated_unit":r.calculated_unit,"limit":r.limit_value,"limit_unit":r.limit_unit,"rule_code":r.rule_code,"rule_version":r.standard_version} for t in x.sessions for r in t.results]
    result["reports"]=[{"id":r.id,"report_number":r.report_number,"status":r.status,"test_session_id":r.test_session_id} for t in x.sessions for r in t.reports]
    result["attachments"]=[{"id":a.id,"filename":a.filename,"content_type":a.content_type,"size_bytes":a.size_bytes,"created_at":a.created_at} for a in db.query(Attachment).filter_by(instrument_id=x.id).all()]
    return result

@router.patch("/{item_id}")
def update(item_id:int,data:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    x=db.get(Instrument,item_id)
    if not x:raise HTTPException(404,"Instrument not found")
    allowed={"manufacturer","model","serial_number","instrument_type","accuracy_class","capacity_unit","max_capacity","min_capacity","verification_interval_e","display_interval_d"}
    if not data or set(data)-allowed:raise HTTPException(422,"Unsupported instrument fields")
    current={k:getattr(x,k) for k in allowed};current.update(data)
    if x.sessions and any(k in data for k in {"accuracy_class","capacity_unit","max_capacity","min_capacity","verification_interval_e","display_interval_d"}):raise HTTPException(409,"Metrological characteristics are locked after a test session exists")
    if "capacity_unit" in data and data["capacity_unit"]!=x.capacity_unit:
        to_kg={"kg":1.0,"g":0.001,"t":1000.0,"mg":0.000001}
        if data["capacity_unit"] not in to_kg:raise HTTPException(422,"Unsupported capacity unit")
        factor=to_kg[x.capacity_unit]/to_kg[data["capacity_unit"]]
        for key in ("max_capacity","min_capacity","verification_interval_e","display_interval_d"):
            if key not in data:current[key]=float(current[key])*factor
    errors=validate_instrument(current)
    if errors:raise HTTPException(422,detail={"message":"Please correct the instrument details.","errors":errors})
    existing=db.query(Instrument).filter(Instrument.serial_number==current["serial_number"],Instrument.id!=x.id).first()
    if existing:raise HTTPException(409,"Serial number is already registered")
    before={k:getattr(x,k) for k in allowed}
    for key in data:setattr(x,key,current[key])
    if "capacity_unit" in data and data["capacity_unit"]!=before["capacity_unit"]:
        for key in ("max_capacity","min_capacity","verification_interval_e","display_interval_d"):
            if key not in data:setattr(x,key,current[key])
    x.number_of_verification_intervals_n=round(float(x.max_capacity)/float(x.verification_interval_e))
    after={k:getattr(x,k) for k in allowed}
    db.add(AuditLog(user_id=u.id,action="INSTRUMENT_UPDATED",entity_type="INSTRUMENT",entity_id=str(x.id),details=f"Before: {before}; after: {after}"));db.commit();db.refresh(x);return output(x)

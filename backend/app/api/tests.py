from datetime import date
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import TestSession, TestObservation, ComplianceResult, Instrument, AuditLog, User
from app.api.deps import current_user, roles
from app.compliance.rule_engine import evaluate_all
from app.db.models import RuleConfiguration
router=APIRouter(prefix="/api/tests",tags=["tests"])
compliance_router=APIRouter(prefix="/api/compliance",tags=["compliance"])
def verify_access(t,u):
    if u.role=="LAB_TECHNICIAN" and t.operator_id!=u.id: raise HTTPException(403,"You can only access your own test sessions")
def require_current_passing_evaluation(t,db):
    current=evaluate_all(t.instrument,t.observations,db.query(RuleConfiguration).filter(RuleConfiguration.active.is_(True)).all())
    saved={r.test_type:r for r in t.results}
    if current["overall_status"]!="PASS" or len(saved)!=5:raise HTTPException(409,"All five test types need active applicable rules and passing evaluations before final review")
    for result in current["results"]:
        old=saved.get(result["test_type"]);rule=result.get("rule") or (result.get("rules") or [None])[0]
        if not old or not rule or old.status!="PASS" or old.rule_code!=rule.rule_code or old.standard_version!=rule.standard_version or old.details!=result["details"] or old.calculated_value!=result["calculated_value"] or old.limit_value!=result["limit"]:
            raise HTTPException(409,"Rules or observations changed after evaluation. Run compliance again before final review.")
def view(t): return {"id":t.id,"instrument_id":t.instrument_id,"instrument":t.instrument.serial_number,"model":t.instrument.model,"operator":t.operator.name,"operator_id":t.operator_id,"status":t.status,"test_date":str(t.test_date),"laboratory":t.laboratory,"temperature":t.temperature,"humidity":t.humidity,"pressure":t.pressure,"remarks":t.remarks,"rejection_reason":t.rejection_reason,"observations":[{"id":o.id,"test_type":o.test_type,"test_point":o.test_point,"applied_load":o.applied_load,"indicated_value":o.indicated_value,"error":o.error,"observation_data":o.observation_data} for o in t.observations],"results":[{"id":r.id,"test_type":r.test_type,"limit_value":r.limit_value,"calculated_value":r.calculated_value,"calculated_unit":r.calculated_unit,"limit_unit":r.limit_unit,"status":r.status,"details":r.details,"standard_name":r.standard_name,"standard_version":r.standard_version,"rule_code":r.rule_code,"rule_description":r.rule_description} for r in t.results]}
@router.get("")
def listing(db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(TestSession)
    if u.role=="LAB_TECHNICIAN": q=q.filter(TestSession.operator_id==u.id)
    return [view(t) for t in q.order_by(TestSession.created_at.desc()).all()]
@router.post("",status_code=201)
def create(d:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    inst=db.get(Instrument,int(d.get("instrument_id",0)))
    if not inst: raise HTTPException(422,"Select a registered instrument")
    test_day=date.fromisoformat(d["test_date"]) if d.get("test_date") else date.today()
    t=TestSession(instrument_id=inst.id,operator_id=u.id,laboratory=d.get("laboratory",""),temperature=d.get("temperature"),humidity=d.get("humidity"),pressure=d.get("pressure"),remarks=d.get("remarks",""),test_date=test_day)
    db.add(t);db.flush();db.add(AuditLog(user_id=u.id,action="TEST_CREATED",entity_type="TEST",entity_id=str(t.id)));db.commit();db.refresh(t);return view(t)
@router.get("/{test_id}")
def detail(test_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=db.get(TestSession,test_id)
    if not t: raise HTTPException(404,"Test session not found")
    verify_access(t,u)
    return view(t)
@router.post("/{test_id}/observations",status_code=201)
def add_observations(test_id:int,d:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    t=db.get(TestSession,test_id)
    if not t: raise HTTPException(404,"Test session not found")
    verify_access(t,u)
    if t.status not in ("DRAFT","IN_PROGRESS","REJECTED"): raise HTTPException(409,"Observations are locked for this workflow status")
    rows=d.get("observations",[])
    if not rows: raise HTTPException(422,"Add at least one observation")
    for row in rows:
        typ=row.get("test_type","WEIGHING").upper()
        if typ not in {"WEIGHING","MPE","REPEATABILITY","ECCENTRICITY","TARE"}: raise HTTPException(422,"Unsupported test type")
        applied=float(row["applied_load"]);indicated=float(row["indicated_value"])
        t.observations.append(TestObservation(test_type=typ,test_point=str(row.get("test_point","")),applied_load=applied,indicated_value=indicated,error=indicated-applied,observation_data=row.get("observation_data",{})))
    t.status="IN_PROGRESS";db.add(AuditLog(user_id=u.id,action="OBSERVATION_UPDATED",entity_type="TEST",entity_id=str(t.id),details=f"Added {len(rows)} observation(s)"));db.commit();return view(t)
@router.post("/{test_id}/run-compliance")
def calculate(test_id:int,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    t=db.get(TestSession,test_id)
    if not t: raise HTTPException(404,"Test session not found")
    verify_access(t,u)
    t.results.clear(); outcome=evaluate_all(t.instrument,t.observations,db.query(RuleConfiguration).filter(RuleConfiguration.active.is_(True)).all())
    versions=sorted({f"{x['rules'][0].standard_name} {x['rules'][0].standard_version}" for x in outcome["results"] if x.get("rules")})
    for r in outcome["results"]:
        rule=r.get("rule") or (r.get("rules") or [None])[0]
        t.results.append(ComplianceResult(test_type=r["test_type"],rule_id=rule.id if rule else None,evaluated_by=u.id,limit_value=r["limit"],limit_unit=rule.unit if rule else "",calculated_value=r["calculated_value"],calculated_unit=r["calculated_unit"],status=r["status"],details=r["details"],standard_name=rule.standard_name if rule else "OIML R-76",standard_version=rule.standard_version if rule else "UNCONFIGURED",rule_code=rule.rule_code if rule else "MISSING_RULE",rule_description=rule.description if rule else r["details"]))
    audit_data={"overall_status":outcome["overall_status"],"active_rule_versions":versions,"results":[{"test_type":r["test_type"],"status":r["status"],"rule_ids":[x.id for x in r.get("rules",[])]} for r in outcome["results"]]}
    db.add(AuditLog(user_id=u.id,action="COMPLIANCE_EVALUATION_RUN",entity_type="TEST",entity_id=str(t.id),details=json.dumps(audit_data)));db.commit();return {"overall_status":outcome["overall_status"],"standard_name":"OIML R-76","standard_version":", ".join(versions) if versions else "UNCONFIGURED","results":[{"test_type":r["test_type"],"calculated_value":r["calculated_value"],"calculated_unit":r["calculated_unit"],"limit":r["limit"],"limit_unit":((r.get("rule") or (r.get("rules") or [None])[0]).unit if (r.get("rule") or r.get("rules")) else ""),"status":r["status"],"details":r["details"],"rule_code":(r.get("rule") or (r.get("rules") or [None])[0]).rule_code if (r.get("rule") or r.get("rules")) else "MISSING_RULE","rule_description":(r.get("rule") or (r.get("rules") or [None])[0]).description if (r.get("rule") or r.get("rules")) else r["details"],"standard_version":(r.get("rule") or (r.get("rules") or [None])[0]).standard_version if (r.get("rule") or r.get("rules")) else "UNCONFIGURED"} for r in outcome["results"]]}
@router.post("/{test_id}/submit")
def submit(test_id:int,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    t=db.get(TestSession,test_id)
    if not t: raise HTTPException(404,"Test session not found")
    verify_access(t,u)
    require_current_passing_evaluation(t,db)
    t.status="UNDER_REVIEW";db.add(AuditLog(user_id=u.id,action="REPORT_SUBMITTED",entity_type="TEST",entity_id=str(t.id),details="All five test types revalidated against current active rule records."));db.commit();return view(t)
@router.post("/{test_id}/review")
def review(test_id:int,d:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","APPROVING_OFFICER"))):
    t=db.get(TestSession,test_id)
    if not t or t.status!="UNDER_REVIEW": raise HTTPException(409,"Test is not awaiting review")
    decision=d.get("decision"); reason=str(d.get("reason",""))
    if decision not in {"APPROVE","REJECT"}: raise HTTPException(422,"Decision must be APPROVE or REJECT")
    if decision=="REJECT" and not reason.strip(): raise HTTPException(422,"A rejection reason is required")
    if decision=="APPROVE":require_current_passing_evaluation(t,db)
    t.status="APPROVED" if decision=="APPROVE" else "REJECTED";t.rejection_reason=reason
    for report in t.reports:report.status=t.status
    db.add(AuditLog(user_id=u.id,action="REPORT_APPROVED" if decision=="APPROVE" else "REPORT_REJECTED",entity_type="TEST",entity_id=str(t.id),details=reason));db.commit();return view(t)

@compliance_router.get("/{test_id}")
def compliance_results(test_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    t=db.get(TestSession,test_id)
    if not t: raise HTTPException(404,"Test session not found")
    verify_access(t,u)
    status="NOT_EVALUATED" if len(t.results)!=5 or any(r.status=="NOT_EVALUATED" for r in t.results) else ("FAIL" if any(r.status=="FAIL" for r in t.results) else ("PASS" if all(r.status=="PASS" for r in t.results) else "NOT_EVALUATED"))
    return {"test_session_id":t.id,"overall_status":status,"results":[{"test_type":r.test_type,"calculated_value":r.calculated_value,"calculated_unit":r.calculated_unit,"limit":r.limit_value,"limit_unit":r.limit_unit,"status":r.status,"details":r.details,"standard_name":r.standard_name,"standard_version":r.standard_version,"rule_code":r.rule_code,"rule_description":r.rule_description} for r in t.results]}

import math
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import RuleConfiguration, AuditLog, User
from app.api.deps import current_user, roles
from app.compliance.engine import TEST_TYPES

router=APIRouter(prefix="/api/rules",tags=["rules"])
CLASSES=("I","II","III","IIII")
OPS={"<=","<",">=",">","=="}
DEMO_VERSION="SIH-DEMO-1.0 (NON-OFFICIAL)"
DEMO_LIMITS={"MPE":0.02,"WEIGHING":0.02,"REPEATABILITY":0.02,"ECCENTRICITY":0.03,"TARE":0.01}
def data(r):return {"id":r.id,"standard_name":r.standard_name,"standard_version":r.standard_version,"rule_code":r.rule_code,"test_type":r.test_type,"accuracy_class":r.accuracy_class,"applicable_range":r.applicable_range,"limit":r.limit_value,"unit":r.unit,"comparison_operator":r.comparison_operator,"description":r.description,"active":r.active,"source_reference":r.source_reference,"created_at":r.created_at,"updated_at":r.updated_at}

def seed_demo_profile_if_empty(db,user_id=None):
    """Seed only a brand-new, unconfigured database with non-official demo rules."""
    existing=db.query(RuleConfiguration).filter(RuleConfiguration.standard_name=="OIML R-76").first()
    if existing:return False
    for test_type,limit in DEMO_LIMITS.items():
        rule=RuleConfiguration(standard_name="OIML R-76",standard_version=DEMO_VERSION,rule_code=f"SIH-DEMO-{test_type}-01",test_type=test_type,accuracy_class="III",applicable_range={"min_load":0.0,"max_load":26.0,"unit":"kg"},limit_value=limit,unit="kg",comparison_operator="<=",description=f"Illustrative SIH demonstration threshold for {test_type}; not an official OIML R-76 limit and not suitable for legal verification.",source_reference="SIH prototype demonstration profile, version 1.0; synthetic configurable value, no official OIML clause claimed",active=True)
        db.add(rule);db.flush()
        db.add(AuditLog(user_id=user_id,action="RULE_CONFIGURATION_CHANGED",entity_type="RULE",entity_id=str(rule.id),details=f"Seeded explicitly non-official {DEMO_VERSION} profile rule {rule.rule_code} on an unconfigured database"))
    db.commit()
    return True

@router.get("")
def listing(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rules=db.query(RuleConfiguration).order_by(RuleConfiguration.standard_version.desc(),RuleConfiguration.test_type,RuleConfiguration.accuracy_class).all()
    active_versions=sorted({f"{x.standard_name} · {x.standard_version}" for x in rules if x.active})
    existing={(x.test_type,x.accuracy_class) for x in rules if x.active and x.standard_name=="OIML R-76"}
    inactive={(x.test_type,x.accuracy_class) for x in rules if not x.active and x.standard_name=="OIML R-76"}
    coverage=[{"test_type":test,"accuracy_class":cls,"status":"CONFIGURED" if (test,cls) in existing else ("INACTIVE" if (test,cls) in inactive else "MISSING")} for test in TEST_TYPES for cls in CLASSES]
    groups={}
    for rule in rules:
        if not rule.active:continue
        key=(rule.standard_name,rule.standard_version)
        group=groups.setdefault(key,[])
        group.append(rule)
    active_rule_sets=[{"id":f"{name}::{version}","standard_name":name,"version":version,"status":"DEMO_CONFIGURED" if version==DEMO_VERSION else "ACTIVE_CONFIGURED","active":True,"rule_count":len(group),"accuracy_classes":sorted({r.accuracy_class for r in group}),"test_types":sorted({r.test_type for r in group}),"non_official":version==DEMO_VERSION} for (name,version),group in sorted(groups.items())]
    return {"rules":[data(x) for x in rules],"coverage":coverage,"active_versions":active_versions,"active_rule_sets":active_rule_sets}

@router.post("/demo-profile",status_code=201)
def load_demo_profile(db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    """Install an explicitly synthetic rule profile for controlled demonstrations."""
    active=db.query(RuleConfiguration).filter(RuleConfiguration.standard_name=="OIML R-76",RuleConfiguration.active.is_(True)).all()
    other_versions={r.standard_version for r in active if r.standard_version!=DEMO_VERSION}
    if other_versions:
        raise HTTPException(409,detail={"message":"An active non-demo OIML rule edition exists. Deactivate it deliberately before loading the demo profile.","active_versions":sorted(other_versions)})
    existing={r.test_type for r in active if r.accuracy_class=="III" and r.standard_version==DEMO_VERSION}
    created=[]
    for test_type,limit in DEMO_LIMITS.items():
        if test_type in existing:continue
        rule=RuleConfiguration(standard_name="OIML R-76",standard_version=DEMO_VERSION,rule_code=f"SIH-DEMO-{test_type}-01",test_type=test_type,accuracy_class="III",applicable_range={"min_load":0.0,"max_load":26.0,"unit":"kg"},limit_value=limit,unit="kg",comparison_operator="<=",description=f"Illustrative SIH demonstration threshold for {test_type}; not an official OIML R-76 limit and not suitable for legal verification.",source_reference="SIH prototype demonstration profile, version 1.0; synthetic configurable value, no official OIML clause claimed",active=True)
        db.add(rule);db.flush();created.append(rule)
        db.add(AuditLog(user_id=u.id,action="RULE_CONFIGURATION_CHANGED",entity_type="RULE",entity_id=str(rule.id),details=f"Created explicitly non-official {DEMO_VERSION} profile rule {rule.rule_code}"))
    db.commit()
    rows=db.query(RuleConfiguration).filter(RuleConfiguration.standard_name=="OIML R-76",RuleConfiguration.standard_version==DEMO_VERSION,RuleConfiguration.accuracy_class=="III",RuleConfiguration.active.is_(True)).all()
    return {"version":DEMO_VERSION,"created":len(created),"rules":[data(r) for r in rows],"notice":"Synthetic SIH demonstration thresholds only. Not official OIML values and not legal certification."}

@router.post("",status_code=201)
def create(body:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    required=("standard_name","standard_version","rule_code","test_type","accuracy_class","limit","unit","comparison_operator","description","source_reference")
    missing=[x for x in required if not str(body.get(x," ")).strip()]
    if missing:raise HTTPException(422,detail={"message":"Complete all rule metadata fields.","errors":[f"{x.replace('_',' ').title()} is required." for x in missing]})
    if body["test_type"] not in TEST_TYPES or body["accuracy_class"] not in CLASSES:raise HTTPException(422,"Unsupported test type or accuracy class")
    if body["comparison_operator"] not in OPS:raise HTTPException(422,"Unsupported comparison operator")
    if "active" in body and not isinstance(body["active"],bool):raise HTTPException(422,"Active must be a boolean")
    try:limit=float(body["limit"])
    except (ValueError,TypeError):raise HTTPException(422,"Rule limit must be a number")
    if not math.isfinite(limit):raise HTTPException(422,"Rule limit must be finite")
    ranges=body.get("applicable_range") or {}
    if not isinstance(ranges,dict):raise HTTPException(422,"Applicable range must be an object")
    if ranges.get("unit") not in {None,"kg","g","t","mg"}:raise HTTPException(422,"Applicable range unit must be kg, g, t or mg")
    try:
        low=ranges.get("min_load");high=ranges.get("max_load")
        if low is not None and high is not None and float(low)>float(high):raise HTTPException(422,"Range minimum cannot exceed maximum")
        for v in (low,high):
            if v is not None and (not math.isfinite(float(v)) or float(v)<0):raise HTTPException(422,"Range values must be finite and non-negative")
    except (ValueError,TypeError):raise HTTPException(422,"Range bounds must be numbers")
    standard=body["standard_name"].strip();version=body["standard_version"].strip()
    deactivated=0
    if body.get("active",True):
        # Prevent ambiguous editions: one active edition per named standard.
        prior=db.query(RuleConfiguration).filter(RuleConfiguration.standard_name==standard,RuleConfiguration.active.is_(True),RuleConfiguration.standard_version!=version).all()
        deactivated=len(prior)
        for old in prior:
            old.active=False;old.updated_at=datetime.utcnow();db.add(AuditLog(user_id=u.id,action="RULE_CONFIGURATION_CHANGED",entity_type="RULE",entity_id=str(old.id),details=f"Deactivated {old.rule_code}; superseded by {standard} {version}"))
    r=RuleConfiguration(standard_name=standard,standard_version=version,rule_code=body["rule_code"].strip(),test_type=body["test_type"],accuracy_class=body["accuracy_class"],applicable_range=ranges,limit_value=limit,unit=body["unit"].strip(),comparison_operator=body["comparison_operator"],description=body["description"].strip(),source_reference=body["source_reference"].strip(),active=bool(body.get("active",True)))
    db.add(r);db.flush();db.add(AuditLog(user_id=u.id,action="RULE_CONFIGURATION_CHANGED",entity_type="RULE",entity_id=str(r.id),details=f"Created {r.rule_code}; {r.standard_name} {r.standard_version}; active={r.active}; prior edition rule records deactivated={deactivated}"));db.commit();db.refresh(r);return data(r)

@router.patch("/{rule_id}")
def update(rule_id:int,body:dict,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN"))):
    r=db.get(RuleConfiguration,rule_id)
    if not r:raise HTTPException(404,"Rule not found")
    if set(body)!={"active"} or not isinstance(body["active"],bool):raise HTTPException(422,"Only the active status can be changed on an existing rule version")
    deactivated=0
    if body["active"]:
        prior=db.query(RuleConfiguration).filter(RuleConfiguration.standard_name==r.standard_name,RuleConfiguration.active.is_(True),RuleConfiguration.standard_version!=r.standard_version).all()
        deactivated=len(prior)
        for old in prior:
            old.active=False;old.updated_at=datetime.utcnow();db.add(AuditLog(user_id=u.id,action="RULE_CONFIGURATION_CHANGED",entity_type="RULE",entity_id=str(old.id),details=f"Deactivated {old.rule_code}; superseded by {r.standard_name} {r.standard_version}"))
    r.active=body["active"];r.updated_at=datetime.utcnow()
    db.add(AuditLog(user_id=u.id,action="RULE_CONFIGURATION_CHANGED",entity_type="RULE",entity_id=str(r.id),details=f"Active set to {r.active}; {r.rule_code} {r.standard_version}; prior edition rule records deactivated={deactivated}"));db.commit();db.refresh(r);return data(r)

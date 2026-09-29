from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Instrument,TestSession,Report,User
from app.api.deps import current_user
router=APIRouter(prefix="/api/dashboard",tags=["dashboard"])
@router.get("/summary")
def summary(db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(TestSession)
    if u.role=="LAB_TECHNICIAN":q=q.filter(TestSession.operator_id==u.id)
    tests=q.order_by(TestSession.created_at.desc()).all()
    passed=failed=not_evaluated=0
    for t in tests:
        statuses=[r.status for r in t.results]
        if len(statuses)!=5 or "NOT_EVALUATED" in statuses:not_evaluated+=1
        elif "FAIL" in statuses:failed+=1
        elif all(s=="PASS" for s in statuses):passed+=1
        else:not_evaluated+=1
    report_query=db.query(Report)
    if u.role=="LAB_TECHNICIAN":report_query=report_query.join(TestSession).filter(TestSession.operator_id==u.id)
    instruments=db.query(Instrument).order_by(Instrument.created_at.desc()).limit(5).all()
    return {"total_instruments":db.query(Instrument).count(),"total_test_sessions":len(tests),"active_test_sessions":sum(t.status in ("DRAFT","IN_PROGRESS") for t in tests),"completed_tests":sum(t.status in ("APPROVED","COMPLETED") for t in tests),"pending_reviews":sum(t.status=="UNDER_REVIEW" for t in tests),"passed":passed,"failed":failed,"not_evaluated":not_evaluated,"reports_generated":report_query.count(),"approved_reports":report_query.filter(Report.status=="APPROVED").count(),"recent_tests":[{"id":t.id,"instrument":t.instrument.serial_number,"model":t.instrument.model,"status":t.status,"test_date":str(t.test_date)} for t in tests[:6]],"recent_instruments":[{"id":i.id,"manufacturer":i.manufacturer,"model":i.model,"serial_number":i.serial_number,"accuracy_class":i.accuracy_class} for i in instruments],"recent_reports":[{"id":r.id,"report_number":r.report_number,"status":r.status} for r in report_query.order_by(Report.created_at.desc()).limit(5)]}

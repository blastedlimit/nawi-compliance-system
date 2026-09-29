import os
from xml.sax.saxutils import escape
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from app.db.database import get_db
from app.db.models import Report,TestSession,Instrument,AuditLog,User
from app.api.deps import current_user,roles
router=APIRouter(prefix="/api/reports",tags=["reports"])
OUT=Path(__file__).resolve().parents[2]/"generated_reports";OUT.mkdir(exist_ok=True)
def make_report(t,r):
    inst=t.instrument; filename=str(r.id)
    pdf=OUT/(filename+".pdf"); docx=OUT/(filename+".docx")
    statuses=[x.status for x in t.results]
    evaluation="NOT_EVALUATED" if len(statuses)!=5 or "NOT_EVALUATED" in statuses else ("FAIL" if "FAIL" in statuses else ("PASS" if all(x=="PASS" for x in statuses) else "NOT_EVALUATED"))
    versions=sorted({x.standard_version for x in t.results if x.standard_version!="UNCONFIGURED"})
    version=", ".join(versions) if versions else "UNCONFIGURED"
    has_missing_rule=any(x.status=="NOT_EVALUATED" and x.rule_code=="MISSING_RULE" for x in t.results)
    finalization=("Compliance evaluation could not be finalized because the applicable OIML R-76 rule configuration is unavailable." if has_missing_rule else "Compliance evaluation could not be finalized because required observations or rule coverage are incomplete.") if evaluation=="NOT_EVALUATED" else "Prototype evaluation record; this report is not an official legal certificate."
    styles=getSampleStyleSheet();story=[Paragraph("NAWI TEST REPORT",styles["Title"]),Paragraph("OIML R-76 based compliance evaluation • Prototype record",styles["Normal"]),Spacer(1,14)]
    fields=[["Instrument identification","Value"],["Manufacturer",inst.manufacturer],["Model / serial",f"{inst.model} / {inst.serial_number}"],["Instrument type",inst.instrument_type],["Class",inst.accuracy_class],["Capacity / min",f"{inst.max_capacity} / {inst.min_capacity} {inst.capacity_unit}"],["e / d / n",f"{inst.verification_interval_e} / {inst.display_interval_d} / {inst.number_of_verification_intervals_n}"],["Laboratory",t.laboratory],["Temperature / humidity / pressure",f"{t.temperature} °C / {t.humidity} %RH / {t.pressure} hPa"],["Test date / operator",f"{t.test_date} / {t.operator.name}"],["Report number",r.report_number],["Status",t.status],["Standard rule version","OIML R-76 / UNCONFIGURED; prototype, not legal certification"]]
    fields.extend([["Evaluation status",evaluation],["Standard","OIML R-76"],["Edition / rule version",version]])
    story.insert(2,Paragraph("Evaluation status: "+evaluation,styles["Heading2"]));story.insert(3,Paragraph(finalization,styles["Normal"]))
    tb=Table(fields,colWidths=[185,330],repeatRows=1);tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12304a")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#cbd5df")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f2f6f9")]),("PADDING",(0,0),(-1,-1),7)]));story += [tb,Spacer(1,14),Paragraph("Test observations",styles["Heading2"])];
    obs=[["Test","Point","Load","Indication","Error"]]+[[o.test_type,o.test_point,str(o.applied_load),str(o.indicated_value),str(o.error)] for o in t.observations]
    story.append(Table(obs,colWidths=[90,95,80,100,90],repeatRows=1,style=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dce8f1")),("GRID",(0,0),(-1,-1),.4,colors.grey),("PADDING",(0,0),(-1,-1),6)])))
    story += [Spacer(1,14),Paragraph("Compliance results",styles["Heading2"])]
    res=[["Test","Value / unit","Limit / unit","Status","Rule","Edition"]]+[[x.test_type,f"{x.calculated_value if x.calculated_value is not None else 'Not available'} {x.calculated_unit}",f"{x.limit_value if x.limit_value is not None else ('Range-specific; see details' if x.status in ('PASS','FAIL') else 'Not configured')} {x.limit_unit}",x.status,x.rule_code,x.standard_version] for x in t.results]
    if len(res)==1: res.append(["No results","Not available","Not configured","NOT_EVALUATED","MISSING_RULE","UNCONFIGURED"])
    story.append(Table(res,colWidths=[67,78,78,81,110,86],repeatRows=1,style=TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dce8f1")),("GRID",(0,0),(-1,-1),.4,colors.grey),("PADDING",(0,0),(-1,-1),6)])))
    for result in t.results:story.append(Paragraph(escape(f"{result.test_type}: {result.details}"),styles["BodyText"]))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont("Helvetica",8);canvas.drawString(40,24,"NAWI Compliance • Prototype record; not a legal certificate");canvas.drawRightString(555,24,f"Page {doc.page}");canvas.restoreState()
    SimpleDocTemplate(str(pdf),pagesize=A4,leftMargin=35,rightMargin=35,topMargin=42,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    d=Document();d.add_heading("NAWI TEST REPORT",0);d.add_paragraph("OIML R-76 based compliance evaluation • Prototype record")
    d.add_heading("Evaluation status: "+evaluation,2);d.add_paragraph(finalization)
    for row in fields[1:]: d.add_paragraph(f"{row[0]}: {row[1]}")
    d.add_heading("Test observations",1);tab=d.add_table(rows=1,cols=5);tab.style="Light Shading Accent 1"
    for cell,val in zip(tab.rows[0].cells,obs[0]):cell.text=val
    for row in obs[1:]:
        cells=tab.add_row().cells
        for cell,val in zip(cells,row):cell.text=val
    d.add_heading("Compliance results",1);result_table=d.add_table(rows=1,cols=6);result_table.style="Light Shading Accent 1"
    for cell,val in zip(result_table.rows[0].cells,res[0]):cell.text=val
    for row in res[1:]:
        cells=result_table.add_row().cells
        for cell,val in zip(cells,row):cell.text=val
    for result in t.results:d.add_paragraph(f"{result.test_type}: {result.details}")
    d.add_paragraph("Prototype record; not a legal certificate.");d.save(docx)
    r.pdf_path=str(pdf);r.docx_path=str(docx)
@router.get("")
def listing(q:str="",status:str="",db:Session=Depends(get_db),u:User=Depends(current_user)):
    query=db.query(Report).join(TestSession)
    if u.role=="LAB_TECHNICIAN":query=query.filter(TestSession.operator_id==u.id)
    if q:query=query.filter((Report.report_number.contains(q))|(TestSession.instrument.has(Instrument.serial_number.contains(q)))|(TestSession.instrument.has(Instrument.model.contains(q))))
    if status:query=query.filter(Report.status==status)
    return [{"id":r.id,"report_number":r.report_number,"status":r.status,"test_session_id":r.test_session_id,"serial_number":r.test_session.instrument.serial_number,"model":r.test_session.instrument.model,"test_date":str(r.test_session.test_date),"created_at":r.created_at} for r in query.order_by(Report.created_at.desc()).all()]
@router.post("/from-test/{test_id}",status_code=201)
def generate(test_id:int,db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN","APPROVING_OFFICER"))):
    t=db.get(TestSession,test_id)
    if not t: raise HTTPException(404,"Test session not found")
    if u.role=="LAB_TECHNICIAN" and t.operator_id!=u.id: raise HTTPException(403,"You can only generate reports for your own tests")
    if not t.results: raise HTTPException(409,"Run compliance before generating a report")
    r=Report(test_session_id=t.id,report_number=f"NAWI-{t.test_date:%Y%m%d}-{uuid4().hex[:6].upper()}",status=t.status);db.add(r);db.flush();make_report(t,r);db.add(AuditLog(user_id=u.id,action="REPORT_GENERATED",entity_type="REPORT",entity_id=str(r.id)));db.commit();return {"id":r.id,"report_number":r.report_number,"pdf_path":r.pdf_path,"docx_path":r.docx_path}
@router.get("/{report_id}")
def detail(report_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    r=db.get(Report,report_id)
    if not r: raise HTTPException(404,"Report not found")
    if u.role=="LAB_TECHNICIAN" and r.test_session.operator_id!=u.id: raise HTTPException(403,"You can only access your own reports")
    return {"id":r.id,"report_number":r.report_number,"status":r.status,"test":r.test_session_id}
@router.get("/{report_id}/{fmt}")
def download(report_id:int,fmt:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if fmt not in ("pdf","docx"): raise HTTPException(404,"Format not found")
    r=db.get(Report,report_id)
    if not r:raise HTTPException(404,"Report not found")
    if u.role=="LAB_TECHNICIAN" and r.test_session.operator_id!=u.id: raise HTTPException(403,"You can only access your own reports")
    path=r.pdf_path if fmt=="pdf" else r.docx_path
    if not path or not Path(path).is_file():raise HTTPException(404,"Report file is not available")
    return FileResponse(path,filename=f"{r.report_number}.{fmt}")

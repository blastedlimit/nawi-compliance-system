import re, zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Attachment, Instrument, TestSession, AuditLog, User
from app.api.deps import current_user, roles

router=APIRouter(prefix="/api/attachments",tags=["attachments"])
STORE=Path(__file__).resolve().parents[2]/"attachments";STORE.mkdir(exist_ok=True)
MAX_SIZE=10*1024*1024
MIMES={".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp",".pdf":"application/pdf",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
def metadata(a):return {"id":a.id,"filename":a.filename,"content_type":a.content_type,"size_bytes":a.size_bytes,"uploaded_by":a.uploaded_by,"instrument_id":a.instrument_id,"test_session_id":a.test_session_id,"created_at":a.created_at}
def can_access_test(t,u):
    if u.role=="LAB_TECHNICIAN" and t.operator_id!=u.id:raise HTTPException(403,"You can only access evidence for your own test sessions")
def valid_file(filename,ctype,blob):
    ext=Path(filename).suffix.lower()
    if ext not in MIMES or ctype!=MIMES[ext]:raise HTTPException(415,"Allowed attachments: JPEG, PNG, WebP, PDF, or DOCX")
    signatures={".jpg":blob.startswith(b"\xff\xd8\xff"),".jpeg":blob.startswith(b"\xff\xd8\xff"),".png":blob.startswith(b"\x89PNG\r\n\x1a\n"),".webp":len(blob)>12 and blob[:4]==b"RIFF" and blob[8:12]==b"WEBP",".pdf":blob.startswith(b"%PDF-")}
    if ext==".docx":
        try:
            with zipfile.ZipFile(BytesIO(blob)) as z:ok="[Content_Types].xml" in z.namelist() and "word/document.xml" in z.namelist()
        except (zipfile.BadZipFile,KeyError):ok=False
    else:ok=signatures[ext]
    if not ok:raise HTTPException(415,"File contents do not match the selected file type")
    return ext
@router.post("",status_code=201)
async def upload(file:UploadFile=File(...),instrument_id:int|None=Form(None),test_session_id:int|None=Form(None),db:Session=Depends(get_db),u:User=Depends(roles("ADMIN","LAB_TECHNICIAN"))):
    if instrument_id is None and test_session_id is None:raise HTTPException(422,"Link the attachment to an instrument or test session")
    inst=db.get(Instrument,instrument_id) if instrument_id else None
    t=db.get(TestSession,test_session_id) if test_session_id else None
    if instrument_id and not inst:raise HTTPException(404,"Instrument not found")
    if test_session_id and not t:raise HTTPException(404,"Test session not found")
    if t:
        can_access_test(t,u)
        if inst and t.instrument_id!=inst.id:raise HTTPException(422,"The selected test session does not belong to this instrument")
        inst=inst or t.instrument
    raw_name=(file.filename or "attachment").replace("\\","/").split("/")[-1]
    safe_name=re.sub(r"[^A-Za-z0-9._ -]","_",raw_name)[:180] or "attachment"
    blob=await file.read(MAX_SIZE+1)
    if not blob:raise HTTPException(422,"The selected file is empty")
    if len(blob)>MAX_SIZE:raise HTTPException(413,"Attachments must be 10 MB or smaller")
    ext=valid_file(safe_name,file.content_type or "",blob);key=uuid4().hex+ext;path=STORE/key
    path.write_bytes(blob)
    item=Attachment(instrument_id=inst.id if inst else None,test_session_id=t.id if t else None,filename=safe_name,file_path=str(path),content_type=MIMES[ext],size_bytes=len(blob),uploaded_by=u.id)
    db.add(item);db.flush();db.add(AuditLog(user_id=u.id,action="ATTACHMENT_UPLOADED",entity_type="ATTACHMENT",entity_id=str(item.id),details=f"{safe_name}; {len(blob)} bytes"));db.commit();db.refresh(item);return metadata(item)
@router.get("")
def listing(instrument_id:int|None=None,test_session_id:int|None=None,db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=db.query(Attachment)
    if instrument_id is not None:q=q.filter(Attachment.instrument_id==instrument_id)
    if test_session_id is not None:q=q.filter(Attachment.test_session_id==test_session_id)
    rows=q.order_by(Attachment.created_at.desc()).all()
    if u.role=="LAB_TECHNICIAN":
        for a in rows:
            if a.test_session_id and a.test_session:can_access_test(a.test_session,u)
    return [metadata(a) for a in rows]
@router.get("/{attachment_id}")
def download(attachment_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    a=db.get(Attachment,attachment_id)
    if not a:raise HTTPException(404,"Attachment not found")
    if a.test_session:can_access_test(a.test_session,u)
    path=Path(a.file_path).resolve()
    if path.parent!=STORE.resolve() or not path.is_file():raise HTTPException(404,"Attachment file is unavailable")
    return FileResponse(path,filename=a.filename,media_type=a.content_type)

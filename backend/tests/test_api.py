import unittest
import os,tempfile
from uuid import uuid4
from io import BytesIO
from pathlib import Path
from docx import Document
_test_directory=tempfile.TemporaryDirectory(prefix="nawi-api-test-")
os.environ["DATABASE_URL"]="sqlite:///"+_test_directory.name.replace("\\","/")+"/test.db"
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import engine
from app.api import attachments,reports
attachments.STORE=Path(_test_directory.name)/"attachments";attachments.STORE.mkdir(exist_ok=True)
reports.OUT=Path(_test_directory.name)/"generated_reports";reports.OUT.mkdir(exist_ok=True)

class ApiTests(unittest.TestCase):
    def test_health_login_dashboard_and_admin_rbac(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/health").status_code,200)
            login=client.post("/api/auth/login",data={"username":"admin@nawi.local","password":"Admin@123"})
            self.assertEqual(login.status_code,200)
            admin={"Authorization":"Bearer "+login.json()["access_token"]}
            self.assertEqual(client.get("/api/dashboard/summary",headers=admin).status_code,200)
            tech=client.post("/api/auth/login",data={"username":"technician@nawi.local","password":"Tech@123"})
            denied=client.get("/api/users",headers={"Authorization":"Bearer "+tech.json()["access_token"]})
            self.assertEqual(denied.status_code,403)
            self.assertEqual(client.post("/api/users",headers={"Authorization":"Bearer "+tech.json()["access_token"]},json={}).status_code,403)
            self.assertEqual(client.post("/api/rules",headers={"Authorization":"Bearer "+tech.json()["access_token"]},json={}).status_code,403)
            serial="T-"+uuid4().hex[:10]
            item=client.post("/api/instruments",headers=admin,json={"manufacturer":"Test Lab","model":"Scale X","serial_number":serial,"instrument_type":"Digital scale","accuracy_class":"III","capacity_unit":"kg","max_capacity":26,"min_capacity":0.2,"verification_interval_e":0.01,"display_interval_d":0.01})
            self.assertEqual(item.status_code,201,item.text)
            self.assertEqual(item.json()["number_of_verification_intervals_n"],2600)
            session=client.post("/api/tests",headers=admin,json={"instrument_id":item.json()["id"],"test_date":"2026-09-28","laboratory":"Demo lab"})
            self.assertEqual(session.status_code,201,session.text)
            tid=session.json()["id"]
            self.assertEqual(client.get(f"/api/tests/{tid}",headers={"Authorization":"Bearer "+tech.json()["access_token"]}).status_code,403)
            self.assertEqual(client.post(f"/api/tests/{tid}/review",headers={"Authorization":"Bearer "+tech.json()["access_token"]},json={"decision":"APPROVE"}).status_code,403)
            self.assertEqual(client.get(f"/api/instruments/{item.json()['id']}",headers=admin).status_code,200)
            self.assertEqual(client.patch(f"/api/instruments/{item.json()['id']}",headers=admin,json={"manufacturer":"Updated Test Lab"}).status_code,200)
            self.assertEqual(client.patch(f"/api/instruments/{item.json()['id']}",headers=admin,json={"accuracy_class":"II"}).status_code,409)
            observation=client.post(f"/api/tests/{tid}/observations",headers=admin,json={"observations":[{"test_type":"WEIGHING","test_point":"1","applied_load":1,"indicated_value":1}]})
            self.assertEqual(observation.status_code,201,observation.text)
            evaluation=client.post(f"/api/tests/{tid}/run-compliance",headers=admin)
            self.assertEqual(evaluation.status_code,200,evaluation.text)
            self.assertEqual(evaluation.json()["overall_status"],"NOT_EVALUATED")
            self.assertEqual(len(evaluation.json()["results"]),5)
            self.assertEqual(client.get(f"/api/compliance/{tid}",headers=admin).status_code,200)
            self.assertEqual(client.post(f"/api/tests/{tid}/submit",headers=admin).status_code,409)
            configured=client.post("/api/rules",headers=admin,json={"standard_name":"OIML R-76","standard_version":"TEST-FIXTURE-ONLY","rule_code":"TEST-MPE-01","test_type":"MPE","accuracy_class":"III","applicable_range":{"max_load":None,"unit":"kg"},"limit":0.1,"unit":"kg","comparison_operator":"<=","description":"Synthetic rule for automated testing only; not an OIML value.","source_reference":"Automated test fixture; not a controlled OIML citation","active":True})
            self.assertEqual(configured.status_code,201,configured.text)
            self.assertEqual(client.get("/api/rules",headers=admin).status_code,200)
            evaluated=client.post(f"/api/tests/{tid}/run-compliance",headers=admin)
            self.assertEqual(evaluated.status_code,200,evaluated.text)
            mpe=next(x for x in evaluated.json()["results"] if x["test_type"]=="MPE")
            self.assertEqual(mpe["status"],"PASS")
            self.assertEqual(mpe["standard_version"],"TEST-FIXTURE-ONLY")
            result=client.get(f"/api/compliance/{tid}",headers=admin).json()["results"]
            self.assertEqual(next(x for x in result if x["test_type"]=="MPE")["standard_version"],"TEST-FIXTURE-ONLY")
            client.post(f"/api/tests/{tid}/observations",headers=admin,json={"observations":[{"test_type":"WEIGHING","test_point":"2","applied_load":1,"indicated_value":1.25}]})
            failed=client.post(f"/api/tests/{tid}/run-compliance",headers=admin).json()
            self.assertEqual(next(x for x in failed["results"] if x["test_type"]=="MPE")["status"],"FAIL")
            summary=client.get("/api/dashboard/summary",headers=admin).json()
            self.assertEqual(summary["not_evaluated"],1)
            self.assertEqual(summary["failed"],0)
            self.assertEqual(client.post(f"/api/tests/{tid}/submit",headers=admin).status_code,409)
            files={"file":("../support.pdf",b"%PDF-1.4\nfixture", "application/pdf")}
            attachment=client.post("/api/attachments",headers=admin,files=files,data={"instrument_id":str(item.json()["id"])})
            self.assertEqual(attachment.status_code,201,attachment.text)
            self.assertEqual(client.get(f"/api/attachments/{attachment.json()['id']}",headers=admin).status_code,200)
            self.assertTrue(client.get("/api/users/audit",headers=admin).json())
            new_user=client.post("/api/users",headers=admin,json={"name":"QA User","email":"qa-"+uuid4().hex[:8]+"@nawi.local","password":"Testing-Password-123","role":"APPROVING_OFFICER"})
            self.assertEqual(new_user.status_code,201,new_user.text)
            self.assertEqual(client.patch(f"/api/users/{new_user.json()['id']}",headers=admin,json={"is_active":False}).status_code,200)
            self.assertEqual(client.post("/api/auth/login",data={"username":new_user.json()["email"],"password":"Testing-Password-123"}).status_code,401)
            report=client.post(f"/api/reports/from-test/{tid}",headers=admin)
            self.assertEqual(report.status_code,201,report.text)
            rid=report.json()["id"]
            self.assertEqual(client.get(f"/api/reports/{rid}/pdf",headers=admin).status_code,200)
            docx_response=client.get(f"/api/reports/{rid}/docx",headers=admin)
            self.assertEqual(docx_response.status_code,200)
            document=Document(BytesIO(docx_response.content))
            text=" ".join(p.text for p in document.paragraphs)
            self.assertIn("NOT_EVALUATED",text)
            self.assertIn("applicable OIML R-76 rule configuration is unavailable",text)
            actions={x["action"] for x in client.get("/api/users/audit",headers=admin).json()}
            self.assertTrue({"RULE_CONFIGURATION_CHANGED","INSTRUMENT_UPDATED","ATTACHMENT_UPLOADED","USER_CREATED","COMPLIANCE_EVALUATION_RUN"}.issubset(actions))

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        _test_directory.cleanup()

if __name__=="__main__":unittest.main()

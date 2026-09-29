import unittest
from types import SimpleNamespace as N
from app.compliance.validation import validate_instrument
from app.compliance.engine import run
from app.compliance.mpe import evaluate as evaluate_mpe
from app.compliance.rule_engine import evaluate_all
from app.api.attachments import valid_file
from app.core.security import hash_password, verify_password

class CoreTests(unittest.TestCase):
    def test_password_hashing(self):
        stored=hash_password("Example@123")
        self.assertNotEqual(stored,"Example@123")
        self.assertTrue(verify_password("Example@123",stored))
        self.assertFalse(verify_password("wrong",stored))
    def test_instrument_validation_and_scale_interval_count(self):
        d=dict(manufacturer="A&D",model="AD-26",serial_number="S1",instrument_type="Platform",accuracy_class="III",capacity_unit="kg",max_capacity=26,min_capacity=.2,verification_interval_e=.01,display_interval_d=.01)
        self.assertEqual(validate_instrument(d),[])
        self.assertEqual(round(d["max_capacity"]/d["verification_interval_e"]),2600)
        d["min_capacity"]=27
        self.assertIn("Minimum capacity cannot exceed maximum capacity.",validate_instrument(d))
    def test_unconfigured_rules_are_never_pass(self):
        out=run(N(),[N(test_type="WEIGHING",applied_load=1,indicated_value=1)])
        self.assertEqual(out["overall_status"],"NOT_EVALUATED")
        self.assertTrue(all(x["status"]!="PASS" for x in out["results"]))
    def test_configured_mpe_uses_matching_load_band(self):
        rules={"mpe_by_load_band":[{"max_load":5,"limit":0.1},{"max_load":None,"limit":0.3}],"rule_code":"LAB-MPE-01","rule_description":"Controlled test fixture"}
        reading=N(applied_load=6,indicated_value=6.2)
        self.assertEqual(evaluate_mpe(N(),[reading],rules)["status"],"PASS")
        reading.indicated_value=6.31
        self.assertEqual(evaluate_mpe(N(),[reading],rules)["status"],"FAIL")
    def test_db_rule_evaluation_missing_pass_fail_and_rule_version(self):
        instrument=N(accuracy_class="III",capacity_unit="kg")
        observation=N(test_type="WEIGHING",applied_load=1,indicated_value=1.05)
        missing=evaluate_all(instrument,[observation],[])
        self.assertEqual(next(r for r in missing["results"] if r["test_type"]=="MPE")["status"],"NOT_EVALUATED")
        rule=N(active=True,standard_name="OIML R-76",standard_version="CONTROLLED-EDITION-X",test_type="MPE",accuracy_class="III",applicable_range={"min_load":None,"max_load":None,"unit":"kg"},comparison_operator="<=",limit_value=.1,unit="kg",rule_code="RULE-001",id=7,description="Controlled test fixture")
        passed=evaluate_all(instrument,[observation],[rule])
        result=next(r for r in passed["results"] if r["test_type"]=="MPE")
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["rule"].standard_version,"CONTROLLED-EDITION-X")
        observation.indicated_value=1.2
        failed=evaluate_all(instrument,[observation],[rule])
        self.assertEqual(next(r for r in failed["results"] if r["test_type"]=="MPE")["status"],"FAIL")
    def test_limit_conversion_from_capacity_unit_to_verification_interval(self):
        instrument=N(accuracy_class="III",capacity_unit="kg",verification_interval_e=0.01,display_interval_d=0.01)
        observation=N(test_type="WEIGHING",applied_load=1,indicated_value=1.05)
        rule=N(active=True,standard_name="OIML R-76",standard_version="FIXTURE",test_type="MPE",accuracy_class="III",applicable_range={"unit":"kg"},comparison_operator="<=",limit_value=5,unit="e",rule_code="MPE-E",id=8,description="test")
        result=next(r for r in evaluate_all(instrument,[observation],[rule])["results"] if r["test_type"]=="MPE")
        self.assertEqual(result["status"],"PASS")
    def test_attachment_type_and_magic_validation(self):
        self.assertEqual(valid_file("evidence.pdf","application/pdf",b"%PDF-1.4 test"),".pdf")
        with self.assertRaises(Exception):valid_file("../../payload.svg","image/svg+xml",b"<svg/>")
        with self.assertRaises(Exception):valid_file("evidence.pdf","application/pdf",b"not a PDF")
    def test_repeatability_spread_and_missing_limit(self):
        rows=[N(test_type="REPEATABILITY",indicated_value=x) for x in (10,10.02,10.01)]
        r=run(N(),rows)["results"][2]
        self.assertAlmostEqual(r["calculated_value"],.02)
        self.assertEqual(r["status"],"NOT_EVALUATED")

if __name__=="__main__":unittest.main()

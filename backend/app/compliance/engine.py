import json
from pathlib import Path
from app.compliance import mpe, weighing, repeatability, eccentricity, tare
TEST_TYPES=("MPE","WEIGHING","REPEATABILITY","ECCENTRICITY","TARE")

def run(instrument, observations, rule_config=None):
    if rule_config is None:
        config=json.loads((Path(__file__).parent/"rules.json").read_text(encoding="utf-8"))
    else:
        config=rule_config
    results=[mpe.evaluate(instrument,[o for o in observations if o.test_type.upper() in {"WEIGHING","MPE"}],config.get("mpe")), weighing.evaluate(instrument,observations,config.get("weighing")), repeatability.evaluate(instrument,observations,config), eccentricity.evaluate(instrument,observations,config), tare.evaluate(instrument,observations,config)]
    statuses={r["status"] for r in results}
    overall="FAIL" if "FAIL" in statuses else ("PASS" if statuses=={"PASS"} else "NOT_EVALUATED")
    return {"overall_status":overall,"standard_name":config.get("standard_name","OIML R-76"),"standard_version":config.get("standard_version","UNCONFIGURED"),"results":results}

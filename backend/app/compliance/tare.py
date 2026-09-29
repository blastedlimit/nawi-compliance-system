def evaluate(instrument, observations, rule_config=None):
    rows=[o for o in observations if o.test_type.upper()=="TARE"]
    cfg=(rule_config or {}).get("tare",{}); limit=cfg.get("max_error")
    error=max((abs(o.indicated_value-o.applied_load) for o in rows),default=None)
    status="NOT_EVALUATED" if error is None or limit is None else ("PASS" if error<=float(limit) else "FAIL")
    return {"test_type":"TARE","calculated_value":error,"limit":limit,"status":status,"rule_code":cfg.get("rule_code","TARE_UNCONFIGURED"),"rule_description":cfg.get("rule_description","Requires configured tare rule."),"details":f"Maximum recorded tare indication error {error if error is not None else 'unavailable'}."}

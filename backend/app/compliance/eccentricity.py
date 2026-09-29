def evaluate(instrument, observations, rule_config=None):
    rows=[o for o in observations if o.test_type.upper()=="ECCENTRICITY"]
    errors=[o.indicated_value-o.applied_load for o in rows]
    spread=max(errors)-min(errors) if len(errors)>=2 else None
    cfg=(rule_config or {}).get("eccentricity",{}); limit=cfg.get("max_error_spread")
    status="NOT_EVALUATED" if spread is None or limit is None else ("PASS" if spread<=float(limit) else "FAIL")
    return {"test_type":"ECCENTRICITY","calculated_value":spread,"limit":limit,"status":status,"rule_code":cfg.get("rule_code","ECCENTRICITY_UNCONFIGURED"),"rule_description":cfg.get("rule_description","Requires configured position/loading rule."),"details":f"{len(rows)} position observations; error spread {spread if spread is not None else 'unavailable'}."}

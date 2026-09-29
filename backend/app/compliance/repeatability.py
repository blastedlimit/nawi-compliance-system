def evaluate(instrument, observations, rule_config=None):
    rows=[o for o in observations if o.test_type.upper()=="REPEATABILITY"]
    values=[o.indicated_value for o in rows]
    spread=max(values)-min(values) if len(values)>=2 else None
    cfg=(rule_config or {}).get("repeatability",{})
    limit=cfg.get("max_spread")
    status=("NOT_EVALUATED" if len(values)<2 or limit is None else ("PASS" if spread<=float(limit) else "FAIL"))
    return {"test_type":"REPEATABILITY","calculated_value":spread,"limit":limit,"status":status,"rule_code":cfg.get("rule_code","REPEATABILITY_UNCONFIGURED"),"rule_description":cfg.get("rule_description","Requires a configured rule and at least two observations."),"details":f"{len(values)} indications; spread {spread if spread is not None else 'unavailable'}."}

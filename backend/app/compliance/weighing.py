def evaluate(instrument, observations, rule_config=None):
    """Evaluate recorded weighing points against an explicitly supplied rule."""
    rows=[o for o in observations if o.test_type.upper() in {"WEIGHING","MPE"}]
    errors=[abs(o.indicated_value-o.applied_load) for o in rows]
    worst=max(errors,default=None)
    cfg=rule_config or {};limit=cfg.get("max_error")
    status="NOT_EVALUATED" if worst is None or limit is None else ("PASS" if worst<=float(limit) else "FAIL")
    return {"test_type":"WEIGHING","calculated_value":worst,"limit":limit,"status":status,"rule_code":cfg.get("rule_code","WEIGHING_UNCONFIGURED"),"rule_description":cfg.get("rule_description","Requires approved, versioned weighing test rules."),"details":f"Maximum absolute error across {len(rows)} weighing points: {worst if worst is not None else 'unavailable'}."}

def evaluate(instrument, observations, rule_config=None):
    """MPE must be configured from the applicable controlled standard edition.
    No tolerance is inferred or hard-coded by this prototype.
    """
    rules = rule_config or {}
    bands = rules.get("mpe_by_load_band")
    if not bands:
        return {"test_type":"MPE","calculated_value":None,"limit":None,"status":"NOT_EVALUATED","rule_code":"MPE_UNCONFIGURED","rule_description":"No approved, versioned MPE rule configuration is installed.","details":"Recorded observations are retained. Configure the applicable edition and instrument-specific MPE bands before evaluation."}
    rows=[];missing=False
    for o in observations:
        load=abs(float(o.applied_load)); error=abs(float(o.indicated_value)-float(o.applied_load))
        band=next((b for b in bands if b.get("max_load") is None or load<=float(b["max_load"])),None)
        if not band or band.get("limit") is None:
            missing=True;rows.append(f"load {load:g}: error {error:g}, no configured band");continue
        limit=float(band["limit"]);passed=error<=limit
        rows.append(f"load {load:g}: error {error:g}, limit {limit:g}, {'PASS' if passed else 'FAIL'}")
    worst=max((abs(float(o.indicated_value)-float(o.applied_load)) for o in observations),default=None)
    failed=any("FAIL" in row for row in rows)
    status="FAIL" if failed else ("NOT_EVALUATED" if missing or not rows else "PASS")
    limits={float(b["limit"]) for b in bands if b.get("limit") is not None}
    limit=next(iter(limits)) if len(limits)==1 else None
    return {"test_type":"MPE","calculated_value":worst,"limit":limit,"status":status,"rule_code":rules.get("rule_code","MPE_CONFIGURED"),"rule_description":rules.get("rule_description","Configured rule"),"details":"; ".join(rows) if rows else "No weighing observations were recorded."}

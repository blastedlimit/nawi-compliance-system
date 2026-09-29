from app.compliance.engine import TEST_TYPES
from decimal import Decimal

OPERATORS={"<=":lambda a,b:a<=b,"<":lambda a,b:a<b,">=":lambda a,b:a>=b,">":lambda a,b:a>b,"==":lambda a,b:a==b}
TO_KG={"kg":1.0,"g":0.001,"t":1000.0,"mg":0.000001}

def _convert(value,source,target,instrument):
    v=Decimal(str(value))
    if source==target:return float(v)
    if source in TO_KG and target in TO_KG:return float(v*Decimal(str(TO_KG[source]))/Decimal(str(TO_KG[target])))
    if source in TO_KG and target in {"e","d"}:
        interval=instrument.verification_interval_e if target=="e" else instrument.display_interval_d
        return float(v*Decimal(str(TO_KG[source]))/Decimal(str(TO_KG[instrument.capacity_unit]))/Decimal(str(interval)))
    if source in {"e","d"} and target in TO_KG:
        interval=instrument.verification_interval_e if source=="e" else instrument.display_interval_d
        return float(v*Decimal(str(interval))*Decimal(str(TO_KG[instrument.capacity_unit]))/Decimal(str(TO_KG[target])))
    return None

def _error(indicated,applied):return float(abs(Decimal(str(indicated))-Decimal(str(applied))))

def _value(test_type, observations):
    if not observations:return None
    errors=[Decimal(str(o.indicated_value))-Decimal(str(o.applied_load)) for o in observations]
    if test_type in {"MPE","WEIGHING","TARE"}:return float(max(abs(e) for e in errors))
    if test_type=="REPEATABILITY":
        if len({float(o.applied_load) for o in observations})!=1:return None
        vals=[Decimal(str(o.indicated_value)) for o in observations]
        return float(max(vals)-min(vals)) if len(vals)>1 else None
    if test_type=="ECCENTRICITY":
        if len({float(o.applied_load) for o in observations})!=1:return None
        return float(max(errors)-min(errors)) if len(errors)>1 else None
    return None

def _in_range(rule, instrument, observation):
    area=rule.applicable_range or {}
    unit=area.get("unit",instrument.capacity_unit)
    if unit!=instrument.capacity_unit:return False
    load=abs(float(observation.applied_load))
    low=area.get("min_load"); high=area.get("max_load")
    return (low is None or load>=float(low)) and (high is None or load<=float(high))

def evaluate_all(instrument, observations, rules):
    results=[]
    for test_type in TEST_TYPES:
        obs=[o for o in observations if o.test_type.upper()=="WEIGHING"] if test_type in {"MPE","WEIGHING"} else [o for o in observations if o.test_type.upper()==test_type]
        raw=_value(test_type,obs)
        candidates=[r for r in rules if r.active and r.standard_name=="OIML R-76" and r.test_type==test_type and r.accuracy_class==instrument.accuracy_class]
        if not candidates:
            results.append({"test_type":test_type,"calculated_value":raw,"calculated_unit":instrument.capacity_unit,"limit":None,"status":"NOT_EVALUATED","rule":None,"details":"Applicable OIML R-76 rule is not configured for this instrument/test."})
            continue
        if not obs or raw is None:
            results.append({"test_type":test_type,"calculated_value":raw,"calculated_unit":instrument.capacity_unit,"limit":None,"status":"NOT_EVALUATED","rule":None,"details":"Required test observations are missing or insufficient to calculate this value."})
            continue
        chosen=[];uncovered=[]
        for observation in obs:
            matches=[r for r in candidates if _in_range(r,instrument,observation)]
            if not matches:uncovered.append(observation);continue
            matches.sort(key=lambda r:(float("inf") if (r.applicable_range or {}).get("max_load") is None else float(r.applicable_range["max_load"]),-r.id))
            chosen.append(matches[0])
        if uncovered or not chosen:
            results.append({"test_type":test_type,"calculated_value":raw,"calculated_unit":instrument.capacity_unit,"limit":None,"status":"NOT_EVALUATED","rule":None,"details":"Applicable OIML R-76 rule is not configured for this instrument/test range."})
            continue
        # Pointwise error tests use the matched point band's limit; grouped tests
        # compare their measured spread/variation with each matched configured rule.
        if test_type in {"MPE","WEIGHING","TARE"}:
            comparisons=[]
            for observation in obs:
                matched=[r for r in candidates if _in_range(r,instrument,observation)]
                matched.sort(key=lambda r:(float("inf") if (r.applicable_range or {}).get("max_load") is None else float(r.applicable_range["max_load"]),-r.id))
                rule=matched[0]
                measured=_error(observation.indicated_value,observation.applied_load)
                measured=_convert(measured,instrument.capacity_unit,rule.unit,instrument)
                if measured is None:
                    comparisons=[];uncovered.append(observation);break
                comparisons.append((rule,measured,OPERATORS[rule.comparison_operator](measured,rule.limit_value)))
        else:
            unique_rules=list({r.id:r for r in chosen}.values())
            comparisons=[]
            for r in unique_rules:
                measured=_convert(raw,instrument.capacity_unit,r.unit,instrument)
                if measured is None:uncovered.extend(obs);break
                comparisons.append((r,measured,OPERATORS[r.comparison_operator](measured,r.limit_value)))
        if uncovered or not comparisons:
            results.append({"test_type":test_type,"calculated_value":raw,"calculated_unit":instrument.capacity_unit,"limit":None,"status":"NOT_EVALUATED","rule":None,"details":"Applicable rule unit cannot be safely compared with the recorded observation unit."})
            continue
        passed=all(x[2] for x in comparisons)
        distinct={r.limit_value for r,_,_ in comparisons}
        rule=chosen[0] if all(r.id==chosen[0].id for r in chosen) else None
        details="; ".join(f"{r.rule_code} ({r.standard_version}): {value:g} {r.unit} {r.comparison_operator} {r.limit_value:g} {r.unit}" for r,value,_ in comparisons)
        results.append({"test_type":test_type,"calculated_value":raw,"calculated_unit":instrument.capacity_unit,"limit":next(iter(distinct)) if len(distinct)==1 else None,"status":"PASS" if passed else "FAIL","rule":rule,"rules":chosen,"details":details})
    statuses={x["status"] for x in results}
    overall="NOT_EVALUATED" if "NOT_EVALUATED" in statuses or len(results)!=5 else ("FAIL" if "FAIL" in statuses else "PASS")
    return {"overall_status":overall,"results":results}

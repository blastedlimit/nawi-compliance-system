def validate_instrument(data):
    errors=[]
    for key in ("manufacturer","model","serial_number","instrument_type","accuracy_class","capacity_unit"):
        if not str(data.get(key, "")).strip(): errors.append(f"{key.replace('_',' ').title()} is required.")
    if data.get("accuracy_class") not in {"I","II","III","IIII"}: errors.append("Choose a supported accuracy class.")
    if data.get("capacity_unit") not in {"kg","g","t","mg"}: errors.append("Choose a supported capacity unit.")
    try:
        mx, mn, e, d = (float(data[k]) for k in ("max_capacity","min_capacity","verification_interval_e","display_interval_d"))
        if mx <= 0: errors.append("Maximum capacity must be greater than zero.")
        if mn < 0: errors.append("Minimum capacity cannot be negative.")
        if mn > mx: errors.append("Minimum capacity cannot exceed maximum capacity.")
        if e <= 0: errors.append("Verification interval e must be greater than zero.")
        if d <= 0: errors.append("Display interval d must be greater than zero.")
        if e > 0 and mx > 0 and abs(mx/e-round(mx/e)) > 1e-7: errors.append("Maximum capacity divided by e must be a whole number.")
    except (ValueError, TypeError, KeyError): errors.append("Capacity values must be valid numbers.")
    return errors

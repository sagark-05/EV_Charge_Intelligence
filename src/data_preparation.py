"""Prepare charging sessions without changing the source or guessing corrections."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

DATE_FORMAT = "%d-%m-%Y %H:%M"
TIMEZONE = "Asia/Kolkata"
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data/raw/EV_Dataset_India.csv"
REQUIRED = ["Session_ID", "Session_Start", "Session_End", "Session_Duration_Min",
            "Day_of_Week", "Month", "Station_ID", "Station_Name", "City", "State",
            "Energy_Delivered_kWh", "Queue_Time_Min", "Vehicle_Battery_kWh", "Charger_Power_kW",
            "Area", "Location_Type", "Port_Count", "Port_ID", "Arrival_Time", "Charging_End",
            "Active_Charging_Duration_Min", "Timezone", "Battery_Level_Start", "Battery_Level_End",
            "Latitude", "Longitude", "Charger_Type"]


FEATURE_DEFINITIONS = {
    "Charging_Date": "Session-start date, YYYY-MM-DD.",
    "Charging_Hour": "Session-start hour, integer 0–23.",
    "Weekday_Index": "Session-start weekday, Monday=0 through Sunday=6.",
    "Weekday_Name": "Session-start weekday, full English name.",
    "Is_Weekend": "Boolean: Saturday or Sunday session start.",
    "Year_Month": "Session-start year and month, YYYY-MM.",
    "Calculated_Session_Duration_Min": "Session end minus start, in minutes of port occupancy.",
}


def numeric_status(values):
    """Classify values without replacing missing data with zero."""
    def classify(value):
        if pd.isna(value) or str(value).strip() == "":
            return "missing"
        try:
            number = float(str(value).strip())
        except (ValueError, OverflowError):
            return "nonnumeric"
        if not math.isfinite(number):
            return "nonfinite"
        return "negative" if number < 0 else "valid"

    status = values.map(classify)
    numbers = pd.Series(float("nan"), index=values.index)
    parsed = status.isin(["valid", "negative", "nonfinite"])
    numbers.loc[parsed] = values.loc[parsed].map(lambda value: float(str(value).strip())).astype(float)
    return numbers, status


def derived_features(start, end):
    """Derive calendar fields and elapsed minutes from parsed timestamps."""
    return pd.DataFrame({
        "Charging_Date": start.dt.strftime("%Y-%m-%d"),
        "Charging_Hour": start.dt.hour.astype("Int64"),
        "Weekday_Index": start.dt.dayofweek.astype("Int64"),
        "Weekday_Name": start.dt.day_name(),
        "Is_Weekend": start.dt.dayofweek.ge(5),
        "Year_Month": start.dt.strftime("%Y-%m"),
        "Calculated_Session_Duration_Min": (end - start).dt.total_seconds() / 60,
    }, index=start.index)


def coverage_summary(start):
    """Describe accepted-start coverage without asserting collection uptime."""
    earliest, latest = start.min(), start.max()
    available = start.notna().any()
    return {
        "earliest_session_start": earliest.strftime(DATE_FORMAT) if available else None,
        "latest_session_start": latest.strftime(DATE_FORMAT) if available else None,
        "timezone": TIMEZONE,
        "first_date": earliest.strftime("%Y-%m-%d") if available else None,
        "last_date": latest.strftime("%Y-%m-%d") if available else None,
        "inclusive_calendar_days": int((latest.normalize() - earliest.normalize()).days + 1) if available else 0,
        "observed_session_dates": int(start.dt.normalize().nunique()),
        "calendar_average_assumption": "Future averages assume complete collection across the inclusive range, including zero-session dates.",
        "limitation": "Observed timestamps do not verify collection uptime or complete first/last-day coverage. Boundary months may be partial; timezone is Asia/Kolkata for the supplied synthetic dataset.",
    }


def file_hash(path):
    """Return a streaming SHA-256 fingerprint."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_timestamp(values):
    """Require exactly DD-MM-YYYY HH:MM; invalid dates become NaT."""
    shape = values.str.fullmatch(r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}", na=False)
    return pd.to_datetime(values.where(shape), format=DATE_FORMAT, errors="coerce").dt.tz_localize(TIMEZONE)


NEW_FEATURE_DEFINITIONS = {
    "Arrival_Date": "Arrival date in Asia/Kolkata, YYYY-MM-DD.",
    "Arrival_Hour": "Local arrival hour, integer 0–23; different from session-start demand.",
    "Calculated_Queue_Time_Min": "Session_Start minus Arrival_Time, in minutes.",
    "Calculated_Active_Charging_Duration_Min": "Charging_End minus Session_Start, in minutes.",
    "Post_Charging_Occupancy_Min": "Session_End minus Charging_End, in minutes.",
    "Station_Port_Key": "Station_ID and Port_ID joined by /; port IDs are local to stations.",
}
FEATURE_DEFINITIONS.update(NEW_FEATURE_DEFINITIONS)


def overlapping_port_sessions(rows, start, end, usable):
    """Flag every participant in overlapping [start,end) port-occupancy intervals."""
    ordered = rows.loc[usable & end.gt(start), ["Station_ID", "Port_ID"]].copy()
    ordered["start"] = start.loc[ordered.index]
    ordered["end"] = end.loc[ordered.index]
    keys = ["Station_ID", "Port_ID"]
    ordered = ordered.sort_values(keys + ["start", "end"], kind="stable")
    ordered["running_end"] = ordered.groupby(keys).end.cummax()
    previous_end = ordered.groupby(keys).running_end.shift()
    next_start = ordered.groupby(keys).start.shift(-1)
    conflict = ordered.start.lt(previous_end) | next_start.lt(ordered.end)
    return pd.Series(rows.index.isin(ordered.index[conflict]), index=rows.index)


def prepare_data(raw):
    """Return accepted, rejected, flagged rows and aggregate quality counts."""
    missing_columns = sorted(set(REQUIRED) - set(raw.columns))
    if missing_columns:
        raise ValueError("Missing required columns: " + ", ".join(missing_columns))
    if {"Source_Row_Number", "Quality_Reasons"} & set(raw.columns):
        raise ValueError("Input uses reserved output metadata column names.")
    raw = raw.copy().reset_index(drop=True)
    duplicate = raw.duplicated(keep="first")
    rows = raw.loc[~duplicate].copy()
    rows.insert(0, "Source_Row_Number", rows.index + 2)
    reasons = {index: [] for index in rows.index}
    rejected_mask = pd.Series(False, index=rows.index)
    counts = {}

    def mark(mask, reason, reject=False):
        mask = mask.fillna(False)
        counts[reason] = int(mask.sum())
        for index in rows.index[mask]:
            reasons[index].append(reason)
        if reject:
            rejected_mask.loc[mask] = True

    missing_counts = {}
    for column in raw.columns:
        if column in FEATURE_DEFINITIONS:
            continue
        missing = rows[column].isna() | rows[column].astype("string").str.strip().eq("")
        missing_counts[column] = int(missing.sum())
        mark(missing, "missing_value:" + column)

    ids_missing = rows.Session_ID.isna() | rows.Session_ID.str.strip().eq("")
    mark(ids_missing, "missing_session_id", reject=True)
    # Compare identifiers as supplied: never silently normalize identifiers.
    conflicts = rows.Session_ID.duplicated(keep=False) & ~ids_missing
    mark(conflicts, "conflicting_session_id", reject=True)
    start = parse_timestamp(rows.Session_Start)
    end = parse_timestamp(rows.Session_End)
    mark(start.isna(), "invalid_session_start", reject=True)
    mark(end.isna(), "invalid_session_end", reject=True)
    mark(end.lt(start), "end_before_start", reject=True)

    mark(rows.Timezone.ne(TIMEZONE), "invalid_timezone", reject=True)
    arrival = parse_timestamp(rows.Arrival_Time)
    charging_end = parse_timestamp(rows.Charging_End)
    mark(arrival.isna(), "invalid_arrival_time", reject=True)
    mark(charging_end.isna(), "invalid_charging_end", reject=True)
    mark(arrival.gt(start), "arrival_after_session_start", reject=True)
    mark(charging_end.lt(start) | charging_end.gt(end), "charging_end_outside_session", reject=True)
    port_count, count_status = numeric_status(rows.Port_Count)
    port_id, port_status = numeric_status(rows.Port_ID)
    bad_port = (count_status.ne("valid") | port_status.ne("valid") | port_count.lt(1)
                | port_id.lt(1) | port_count.mod(1).ne(0) | port_id.mod(1).ne(0) | port_id.gt(port_count))
    mark(bad_port, "invalid_port_assignment", reject=True)
    # Station identity is necessary to validate a station-local port.
    mark(rows.Station_ID.isna() | rows.Station_ID.str.strip().eq(""), "missing_station_id", reject=True)
    # Normalize numeric port spelling only for overlap matching, never source IDs.
    port_keys = rows.assign(Port_ID=port_id.where(~bad_port).astype("Int64").astype("string"))
    overlap = overlapping_port_sessions(port_keys, start, end, ~rejected_mask)
    rows["Port_Overlap_Flag"] = overlap
    mark(overlap, "overlapping_port_session")
    active_calculated = (charging_end - start).dt.total_seconds() / 60
    active_recorded, active_status = numeric_status(rows.Active_Charging_Duration_Min)
    mark(active_status.ne("valid"), "invalid_active_charging_duration")
    mark(active_calculated.notna() & active_status.eq("valid")
         & active_recorded.sub(active_calculated).abs().gt(0.01), "active_charging_duration_mismatch")
    queue_calculated = (start - arrival).dt.total_seconds() / 60
    queue_recorded, queue_status = numeric_status(rows.Queue_Time_Min)
    mark(queue_calculated.notna() & queue_status.eq("valid")
         & queue_recorded.sub(queue_calculated).abs().gt(0.01), "queue_time_mismatch")

    duration = pd.to_numeric(rows.Session_Duration_Min, errors="coerce")
    calculated = (end - start).dt.total_seconds() / 60
    mark(duration.isna() | ~duration.abs().lt(float("inf")), "invalid_recorded_duration")
    mark(calculated.notna() & duration.notna() & (duration - calculated).abs().gt(0.01),
         "duration_mismatch")
    mark(start.notna() & rows.Day_of_Week.ne(start.dt.day_name()), "weekday_mismatch")
    month = pd.to_numeric(rows.Month, errors="coerce")
    mark(start.notna() & (month.isna() | month.ne(start.dt.month)), "month_mismatch")

    measurement_summary = {}
    numeric_values = {}
    for column in ["Energy_Delivered_kWh", "Queue_Time_Min"]:
        numeric, status = numeric_status(rows[column])
        numeric_values[column] = numeric.where(status.eq("valid"))
        rows[column + "_Validity"] = status
        for issue in ["missing", "nonnumeric", "nonfinite", "negative"]:
            mark(status.eq(issue), column + ":" + issue)
        measurement_summary[column] = {
            "after_deduplication": {label: int(status.eq(label).sum()) for label in
                                    ["valid", "missing", "nonnumeric", "nonfinite", "negative"]},
            "accepted": {label: int((status.eq(label) & ~rejected_mask).sum()) for label in
                         ["valid", "missing", "nonnumeric", "nonfinite", "negative"]},
        }

    energy = numeric_values["Energy_Delivered_kWh"]
    capacity, capacity_status = numeric_status(rows.Vehicle_Battery_kWh)
    power, power_status = numeric_status(rows.Charger_Power_kW)
    # Energy limits use calculated active charging, excluding post-charge occupancy.
    nominal_energy = power * active_calculated / 60
    capacity_check = energy.notna() & capacity_status.eq("valid")
    power_check = (energy.notna() & power_status.eq("valid") & active_calculated.ge(0)
                   & nominal_energy.abs().lt(float("inf")))
    plausibility = {}
    for flag, eligible, comparison in [
        ("Energy_Exceeds_Battery_Capacity", capacity_check, energy.sub(capacity).gt(1e-6)),
        ("Energy_Exceeds_Nominal_Charger_Energy", power_check, energy.sub(nominal_energy).gt(1e-6)),
    ]:
        rows[flag] = (eligible & comparison).astype("boolean").where(eligible, pd.NA)
        mark(eligible & comparison, "plausibility:" + flag)
        plausibility[flag] = {
            "flagged_after_deduplication": int((eligible & comparison).sum()),
            "flagged_accepted": int((eligible & comparison & ~rejected_mask).sum()),
            "not_evaluable_after_deduplication": int((~eligible).sum()),
            "not_evaluable_accepted": int((~eligible & ~rejected_mask).sum()),
        }

    battery_start, start_status = numeric_status(rows.Battery_Level_Start)
    battery_end, end_status = numeric_status(rows.Battery_Level_End)
    soc_valid = (start_status.eq("valid") & end_status.eq("valid")
                 & battery_start.le(100) & battery_end.le(100) & battery_end.ge(battery_start))
    mark(~soc_valid, "invalid_battery_levels")
    mark(capacity_status.ne("valid") | capacity.le(0), "invalid_battery_capacity")
    mark(power_status.ne("valid") | power.le(0), "invalid_charger_power")
    expected_energy = capacity * (battery_end - battery_start) / 100
    mark(soc_valid & capacity_status.eq("valid") & energy.notna()
         & energy.sub(expected_energy).abs().gt(0.01 + 1e-6), "energy_battery_delta_mismatch")
    station_conflicts = {}
    station_present = rows.Station_ID.notna() & rows.Station_ID.str.strip().ne("")
    for column in ["Station_Name", "City", "State", "Area", "Location_Type", "Latitude",
                   "Longitude", "Port_Count", "Charger_Type", "Charger_Power_kW"]:
        known = rows[column].where(rows[column].notna() & rows[column].str.strip().ne(""))
        distinct = known[station_present].groupby(rows.loc[station_present, "Station_ID"]).nunique()
        ambiguous = distinct.index[distinct.gt(1)]
        station_conflicts[column] = len(ambiguous)
        mark(station_present & rows.Station_ID.isin(ambiguous), "station_multiple:" + column)

    rows["Quality_Reasons"] = [";".join(reasons[index]) for index in rows.index]
    # Format only valid timestamps; retain invalid source text for diagnosis.
    for column, parsed in [("Session_Start", start), ("Session_End", end), ("Arrival_Time", arrival), ("Charging_End", charging_end)]:
        rows.loc[parsed.notna(), column] = parsed[parsed.notna()].dt.strftime(DATE_FORMAT)
    accepted = rows.loc[~rejected_mask].drop(columns="Quality_Reasons")
    features = derived_features(start.loc[~rejected_mask], end.loc[~rejected_mask])
    for column in features:
        accepted[column] = features[column]
    accepted["Arrival_Date"] = arrival.loc[accepted.index].dt.strftime("%Y-%m-%d")
    accepted["Arrival_Hour"] = arrival.loc[accepted.index].dt.hour.astype("Int64")
    accepted["Calculated_Queue_Time_Min"] = queue_calculated.loc[accepted.index]
    accepted["Calculated_Active_Charging_Duration_Min"] = active_calculated.loc[accepted.index]
    accepted["Post_Charging_Occupancy_Min"] = (end - charging_end).dt.total_seconds().loc[accepted.index] / 60
    accepted["Station_Port_Key"] = rows.loc[accepted.index, "Station_ID"] + "/" + rows.loc[accepted.index, "Port_ID"]
    rejected = rows.loc[rejected_mask].copy()
    flagged = rows.loc[rows.Quality_Reasons.ne("")].copy()
    reconciliation = {"input_rows": len(raw), "exact_duplicates_removed": int(duplicate.sum()),
                      "rejected_rows": len(rejected), "accepted_rows": len(accepted)}
    reconciliation["balanced"] = len(raw) == int(duplicate.sum()) + len(rejected) + len(accepted)
    report = {"provenance": "Generated synthetic Indian charging data supplied by the team; generator code, seed and reuse licence not supplied.",
              "timezone": "Asia/Kolkata; explicit local-wall-time parsing and localization; CSV exports retain DD-MM-YYYY HH:MM plus Timezone.",
              "reconciliation": reconciliation, "flagged_rows": len(flagged),
              "reason_counts": counts, "missing_values_by_column_after_deduplication": missing_counts,
              "repeated_session_id_groups_after_deduplication": int(rows.loc[conflicts, "Session_ID"].nunique()),
              "station_ids_with_multiple_values": station_conflicts,
              "policy": {"exact_duplicates": "Keep first input occurrence; compare all original fields.",
                         "flagged_output": "Includes accepted and rejected records with any quality reason.",
                         "source_row_number": "1-based CSV record number including header; not physical line for multiline fields.",
                         "duration_tolerance_minutes": 0.01,
                         "validation_scope": "Reason counts use rows after exact deduplication; station checks include rejected rows."}}
    report.update({
        "coverage": coverage_summary(start.loc[~rejected_mask]),
        "port_validation": {"overlapping_rows": int(overlap.sum()),
                            "overlapping_station_port_pairs": int(port_keys.loc[overlap, ["Station_ID", "Port_ID"]].drop_duplicates().shape[0]),
                            "policy": "Station-local ports; occupancy intervals [Session_Start, Session_End). Touching endpoints allowed. All overlap participants flagged, not silently discarded."},
        "synthetic_assumptions": "Supplied generated Indian data: local Asia/Kolkata times, named station/area/location categories, station-local integer ports, separate arrival/active charging/occupancy. Generator seed, distributions, losses and licence not provided; constraints are checked against CSV values, not invented.",
        "derived_features": FEATURE_DEFINITIONS,
        "existing_derived_columns_recomputed": [c for c in FEATURE_DEFINITIONS if c in raw.columns],
        "derived_feature_policy": "Accepted records always recompute these columns from explicitly parsed timestamps, replacing supplied derived values. Exact duplicates still compare all supplied original fields.",
        "measurement_validity": measurement_summary,
        "measurement_policy": {
            "units": {"Energy_Delivered_kWh": "kWh", "Queue_Time_Min": "minutes"},
            "valid": "Finite numeric value >= 0; zero allowed. Blank/null is missing; explicit NaN/infinity text is nonfinite; other unparseable text is nonnumeric; finite values < 0 are negative.",
            "demand_eligibility": "Measurement validity and plausibility flags never reject a demand row; missing values are never zero-filled.",
            "plausibility": "Compare valid energy against finite nonnegative battery kWh and nominal charger kW times calculated active charging minutes / 60 (Charging_End minus Session_Start; 1e-6 kWh comparison tolerance). Nullable flags: blank means not evaluable. Concerns do not invalidate basic numeric energy validity or cause exclusion.",
            "limitations": "Synthetic consistency checks, not verification of real equipment or observations. Occupancy and active charging are separate. No physical corrections or invented upper cutoffs.",
        },
        "plausibility_concerns": plausibility,
    })
    return accepted, rejected, flagged, report


def run_pipeline(input_path, processed_dir, quality_dir):
    """Read text fields, validate, export artifacts, and verify source integrity."""
    input_path, processed_dir, quality_dir = map(Path, (input_path, processed_dir, quality_dir))
    destinations = [processed_dir / "charging_sessions.csv", processed_dir / "rejected_sessions.csv",
                    quality_dir / "flagged_records.csv", quality_dir / "quality_report.json"]
    if input_path.resolve() in [path.resolve() for path in destinations]:
        raise ValueError("An output path would overwrite the input CSV.")
    before = file_hash(input_path)
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    accepted, rejected, flagged, report = prepare_data(raw)
    after = file_hash(input_path)
    if before != after:
        raise ValueError("Source CSV changed while preparing data; outputs were not written.")
    report["source_dataset"] = input_path.name
    report["source_integrity"] = {"sha256_before": before, "sha256_after": after, "unchanged": True}
    for path in destinations:
        path.parent.mkdir(parents=True, exist_ok=True)
    for frame, path in zip([accepted, rejected, flagged], destinations):
        frame.to_csv(path, index=False)
    destinations[-1].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    """Command-line entry point with project-relative defaults."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--processed-dir", type=Path, default=root / "data/processed")
    parser.add_argument("--quality-dir", type=Path, default=root / "outputs/data_quality")
    args = parser.parse_args()
    try:
        report = run_pipeline(args.input, args.processed_dir, args.quality_dir)
    except (OSError, ValueError, pd.errors.ParserError) as error:
        parser.exit(1, f"Data preparation failed: {error}\n")
    print(json.dumps(report["reconciliation"], indent=2))


if __name__ == "__main__":
    main()

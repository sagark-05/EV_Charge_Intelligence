"""Prepare charging sessions without changing the source or guessing corrections."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

DATE_FORMAT = "%d-%m-%Y %H:%M"
REQUIRED = ["Session_ID", "Session_Start", "Session_End", "Session_Duration_Min",
            "Day_of_Week", "Month", "Station_ID", "Station_Name", "City", "State",
            "Energy_Delivered_kWh", "Queue_Time_Min", "Vehicle_Battery_kWh", "Charger_Power_kW"]


FEATURE_DEFINITIONS = {
    "Charging_Date": "Session-start date, YYYY-MM-DD.",
    "Charging_Hour": "Session-start hour, integer 0–23.",
    "Weekday_Index": "Session-start weekday, Monday=0 through Sunday=6.",
    "Weekday_Name": "Session-start weekday, full English name.",
    "Is_Weekend": "Boolean: Saturday or Sunday session start.",
    "Year_Month": "Session-start year and month, YYYY-MM.",
    "Calculated_Session_Duration_Min": "Session end minus start, in minutes; not active charging time.",
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
        "first_date": earliest.strftime("%Y-%m-%d") if available else None,
        "last_date": latest.strftime("%Y-%m-%d") if available else None,
        "inclusive_calendar_days": int((latest.normalize() - earliest.normalize()).days + 1) if available else 0,
        "observed_session_dates": int(start.dt.normalize().nunique()),
        "calendar_average_assumption": "Future averages assume complete collection across the inclusive range, including zero-session dates.",
        "limitation": "Observed timestamps do not verify collection uptime or complete first/last-day coverage. Boundary months may be partial; timezone is unverified.",
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
    return pd.to_datetime(values.where(shape), format=DATE_FORMAT, errors="coerce")


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
    # Use elapsed timestamp duration, never an assumed active-charging duration.
    nominal_energy = power * calculated / 60
    capacity_check = energy.notna() & capacity_status.eq("valid")
    power_check = (energy.notna() & power_status.eq("valid") & calculated.ge(0)
                   & nominal_energy.abs().lt(float("inf")))
    plausibility = {}
    for flag, eligible, comparison in [
        ("Energy_Exceeds_Battery_Capacity", capacity_check, energy.gt(capacity)),
        ("Energy_Exceeds_Nominal_Charger_Energy", power_check, energy.gt(nominal_energy)),
    ]:
        rows[flag] = (eligible & comparison).astype("boolean").where(eligible, pd.NA)
        mark(eligible & comparison, "plausibility:" + flag)
        plausibility[flag] = {
            "flagged_after_deduplication": int((eligible & comparison).sum()),
            "flagged_accepted": int((eligible & comparison & ~rejected_mask).sum()),
            "not_evaluable_after_deduplication": int((~eligible).sum()),
            "not_evaluable_accepted": int((~eligible & ~rejected_mask).sum()),
        }

    station_conflicts = {}
    station_present = rows.Station_ID.notna() & rows.Station_ID.str.strip().ne("")
    for column in ["Station_Name", "City", "State"]:
        known = rows[column].where(rows[column].notna() & rows[column].str.strip().ne(""))
        distinct = known[station_present].groupby(rows.loc[station_present, "Station_ID"]).nunique()
        ambiguous = distinct.index[distinct.gt(1)]
        station_conflicts[column] = len(ambiguous)
        mark(station_present & rows.Station_ID.isin(ambiguous), "station_multiple:" + column)

    rows["Quality_Reasons"] = [";".join(reasons[index]) for index in rows.index]
    # Format only valid timestamps; retain invalid source text for diagnosis.
    for column, parsed in [("Session_Start", start), ("Session_End", end)]:
        rows.loc[parsed.notna(), column] = parsed[parsed.notna()].dt.strftime(DATE_FORMAT)
    accepted = rows.loc[~rejected_mask].drop(columns="Quality_Reasons")
    features = derived_features(start.loc[~rejected_mask], end.loc[~rejected_mask])
    for column in FEATURE_DEFINITIONS:
        accepted[column] = features[column]
    rejected = rows.loc[rejected_mask].copy()
    flagged = rows.loc[rows.Quality_Reasons.ne("")].copy()
    reconciliation = {"input_rows": len(raw), "exact_duplicates_removed": int(duplicate.sum()),
                      "rejected_rows": len(rejected), "accepted_rows": len(accepted)}
    reconciliation["balanced"] = len(raw) == int(duplicate.sum()) + len(rejected) + len(accepted)
    report = {"provenance": "shared by team member; original source and licence unverified",
              "timezone": "Unverified; timestamps are timezone-naive; no conversion performed.",
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
        "derived_features": FEATURE_DEFINITIONS,
        "existing_derived_columns_recomputed": [c for c in FEATURE_DEFINITIONS if c in raw.columns],
        "derived_feature_policy": "Accepted records always recompute these columns from explicitly parsed timestamps, replacing supplied derived values. Exact duplicates still compare all supplied original fields.",
        "measurement_validity": measurement_summary,
        "measurement_policy": {
            "units": {"Energy_Delivered_kWh": "kWh", "Queue_Time_Min": "minutes"},
            "valid": "Finite numeric value >= 0; zero allowed. Blank/null is missing; explicit NaN/infinity text is nonfinite; other unparseable text is nonnumeric; finite values < 0 are negative.",
            "demand_eligibility": "Measurement validity and plausibility flags never reject a demand row; missing values are never zero-filled.",
            "plausibility": "Compare valid energy against finite nonnegative battery kWh and nominal charger kW times calculated elapsed minutes / 60. Nullable flags: blank means not evaluable. Concerns do not invalidate basic numeric energy validity or cause exclusion.",
            "limitations": "Field definitions, losses and equipment information are unverified; elapsed duration is not active charging time. No physical corrections or invented upper cutoffs.",
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
    parser.add_argument("--input", type=Path, default=root / "data/raw/EV_Dataset.csv")
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

"""Calendar-normalized session-start demand and recorded-energy summaries."""
import argparse
import json
import math
from pathlib import Path

import pandas as pd

try:  # Support both `python -m src.demand_analysis` and direct script execution.
    from .data_preparation import coverage_summary, file_hash, numeric_status, parse_timestamp, TIMEZONE, DEFAULT_INPUT
except ImportError:
    from data_preparation import coverage_summary, file_hash, numeric_status, parse_timestamp, TIMEZONE, DEFAULT_INPUT

ENERGY = "Energy_Delivered_kWh"
FLAGS = ["Energy_Exceeds_Battery_Capacity", "Energy_Exceeds_Nominal_Charger_Energy"]
STATUSES = ["valid", "missing", "nonnumeric", "nonfinite", "negative"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LOCATION_TYPES = ["Workplace", "Residential", "Retail", "Highway"]
CHARGER_TYPES = ["AC Slow", "AC Fast", "DC Fast"]
TIME_PERIODS = ["Overnight", "Morning", "Afternoon", "Evening", "Late night"]
PERIOD_BOUNDARIES = [0, 6, 12, 17, 22, 24]
EXTRA_TABLE_NAMES = ["location_type_hourly", "daily_weekday_counts", "weekday_variability",
                     "time_period_energy", "charger_type_comparison"]
REQUIRED = ["Session_ID", "Session_Start", "Session_End", "Charging_End", "Location_Type",
            "Charger_Type", "Timezone", ENERGY, ENERGY + "_Validity", *FLAGS]
LIMITATIONS = [
    "Generated synthetic Indian charging data; generator code, seed and reuse licence not supplied. Timestamps use Asia/Kolkata.",
    "Complete collection across the inclusive date range, including zero-session dates, is assumed, not verified uptime.",
    "First/last days may be partially observed; full calendar boundary months do not prove full collection.",
    "Full recorded session energy is assigned to session-start time, not a measured hourly electricity-load profile.",
    "Session counts and the project-defined relative index do not establish congestion or true utilization; Peak_Hour labels are unused.",
    "Sensitivity exclusions can change sample composition; this is not corrected or ground-truth data.",
    "Blank plausibility flags mean not evaluable; such rows are retained unless the other flag is true.",
    "Station consistency is checked in preparation; synthetic station mappings do not establish real locations or capacity availability.",
]


def parse_boolean_flags(values, name):
    """Read exported True/False/blank values explicitly into nullable booleans."""
    text = values.astype("string").str.strip().str.lower()
    missing = text.isna() | text.eq("")
    bad = ~missing & ~text.isin(["true", "false"])
    if bad.any():
        raise ValueError(f"{name}: {int(bad.sum())} invalid boolean values; expected True, False or blank.")
    return text.map({"true": True, "false": False}).astype("boolean")


def validate_sessions(raw):
    """Validate identity/quality schema; recompute time and numeric eligibility."""
    missing = sorted(set(REQUIRED) - set(raw.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if raw.empty:
        raise ValueError("Input must contain at least one charging session.")
    raw = raw.reset_index(drop=True)
    ids = raw.Session_ID.astype("string")
    if (ids.isna() | ids.str.strip().eq("")).any():
        raise ValueError("Session_ID must be nonblank for every session.")
    if ids.duplicated().any():
        raise ValueError("Session_ID must be unique; run preparation to resolve duplicates.")
    start = parse_timestamp(raw.Session_Start.astype("string"))
    if start.isna().any():
        raise ValueError(f"Session_Start: {int(start.isna().sum())} invalid timestamps; expected DD-MM-YYYY HH:MM.")
    if not raw.Timezone.eq(TIMEZONE).all():
        raise ValueError("Timezone must be Asia/Kolkata for every session.")
    for column, categories in [("Location_Type", LOCATION_TYPES), ("Charger_Type", CHARGER_TYPES)]:
        if not raw[column].isin(categories).all():
            raise ValueError(f"{column} must contain only documented categories: {', '.join(categories)}.")
    end = parse_timestamp(raw.Session_End.astype("string"))
    charging_end = parse_timestamp(raw.Charging_End.astype("string"))
    if end.isna().any() or charging_end.isna().any():
        raise ValueError("Session_End and Charging_End must be valid DD-MM-YYYY HH:MM timestamps.")
    if (end.lt(start) | charging_end.lt(start) | charging_end.gt(end)).any():
        raise ValueError("Require Session_Start <= Charging_End <= Session_End.")
    declared = raw[ENERGY + "_Validity"].astype("string")
    if not declared.isin(STATUSES).all():
        raise ValueError("Energy_Delivered_kWh_Validity contains missing or undocumented status values.")
    energy, status = numeric_status(raw[ENERGY])
    data = pd.DataFrame({
        "Session_ID": ids, "Session_Start": start,
        "Charging_Date": start.dt.strftime("%Y-%m-%d"),
        "Charging_Hour": start.dt.hour, "Weekday_Index": start.dt.dayofweek,
        "Year_Month": start.dt.strftime("%Y-%m"),
        "Day_Type": start.dt.dayofweek.ge(5).map({False: "Weekday", True: "Weekend"}),
        "Valid_Energy": status.eq("valid"), "Recorded_Energy_kWh": energy.where(status.eq("valid")),
    })
    data["Active_Duration_Min"] = (charging_end - start).dt.total_seconds() / 60
    data["Connected_Duration_Min"] = (end - start).dt.total_seconds() / 60
    duration_mismatches = {}
    for supplied, calculated in [("Active_Charging_Duration_Min", "Active_Duration_Min"),
                                  ("Session_Duration_Min", "Connected_Duration_Min")]:
        mismatch = pd.Series(False, index=data.index)
        if supplied in raw:
            recorded, recorded_status = numeric_status(raw[supplied])
            mismatch = recorded_status.ne("valid") | recorded.sub(data[calculated]).abs().gt(0.01)
        duration_mismatches[supplied] = {"supplied": supplied in raw, "mismatches": int(mismatch.sum())}
        data[supplied + "_Mismatch"] = mismatch
    for column in ["Area", "Location_Type", "Charger_Type", "Port_ID", "Port_Count", "Arrival_Time", "Charging_End",
                   "Active_Charging_Duration_Min", "Calculated_Active_Charging_Duration_Min", "Timezone"]:
        if column in raw:
            data[column] = raw[column]
    for flag in FLAGS:
        data[flag] = parse_boolean_flags(raw[flag], flag)
    data["Sensitivity_Excluded"] = data[FLAGS].fillna(False).any(axis=1)
    metadata = {
        "duration_consistency": duration_mismatches,
        "duration_policy": "Recompute active and connected minutes from local timestamps; report supplied-field mismatches without discarding demand rows.",
        "energy_validity_counts": {label: int(status.eq(label).sum()) for label in STATUSES},
        "declared_energy_validity_mismatch_count": int(declared.ne(status).sum()),
        "energy_policy": "Recomputed numeric status determines eligibility; declared-status mismatches are reported, never used to drop demand rows.",
        "temporal_policy": "All analysis calendar features are recomputed from explicitly parsed Session_Start; supplied derived features are not trusted or modified.",
        "plausibility_flags": {flag: {"true": int(data[flag].eq(True).sum()),
                                       "false": int(data[flag].eq(False).sum()),
                                       "not_evaluable": int(data[flag].isna().sum())} for flag in FLAGS},
        "overlapping_flags_count": int(data[FLAGS].fillna(False).all(axis=1).sum()),
        "plausibility_union_count": int(data.Sensitivity_Excluded.sum()),
        "valid_energy_plausibility_union_count": int((data.Sensitivity_Excluded & data.Valid_Energy).sum()),
    }
    return data, metadata


def build_calendar(start):
    """Build all represented dates, including dates with zero recorded starts."""
    dates = pd.Series(pd.date_range(start.min().normalize(), start.max().normalize(), freq="D"))
    return pd.DataFrame({
        "Charging_Date": dates.dt.strftime("%Y-%m-%d"),
        "Weekday_Index": dates.dt.dayofweek,
        "Day_Type": dates.dt.dayofweek.ge(5).map({False: "Weekday", True: "Weekend"}),
        "Year_Month": dates.dt.strftime("%Y-%m"),
        "Days_In_Month": dates.dt.days_in_month,
    })


def summarize_groups(data, keys, index, calendar_days):
    """Aggregate starts and eligible energy over an explicit ordered category grid."""
    grouped = data.groupby(keys, sort=False)
    result = grouped.agg(session_count=("Session_ID", "size"),
                         valid_energy_session_count=("Valid_Energy", "sum"))
    result["total_recorded_energy_kwh"] = grouped.Recorded_Energy_kWh.sum(min_count=1)
    result = result.reindex(index)
    for column in ["session_count", "valid_energy_session_count"]:
        result[column] = result[column].fillna(0).astype("int64")
    result["invalid_energy_session_count"] = result.session_count - result.valid_energy_session_count
    result["calendar_days"] = calendar_days
    days = result.calendar_days.replace(0, float("nan"))
    result["avg_sessions_per_day"] = result.session_count / days
    result["avg_recorded_energy_per_valid_session_kwh"] = (
        result.total_recorded_energy_kwh / result.valid_energy_session_count.replace(0, float("nan")))
    result["avg_recorded_energy_per_day_kwh"] = result.total_recorded_energy_kwh / days
    result["energy_observation_status"] = "valid_energy_observed"
    result.loc[result.valid_energy_session_count.eq(0), "energy_observation_status"] = "no_valid_energy"
    result.loc[result.session_count.eq(0), "energy_observation_status"] = "no_sessions"
    return result.reset_index()


def build_demand_tables(data, calendar):
    """Create six ordered tables with denominators from represented calendar dates."""
    days = len(calendar)
    weekday_days = calendar.groupby("Weekday_Index").size().reindex(range(7), fill_value=0)
    type_days = calendar.groupby("Day_Type").size().reindex(["Weekday", "Weekend"], fill_value=0)
    months = calendar.groupby("Year_Month", sort=True).size()
    day_hour = pd.MultiIndex.from_product([range(7), range(24)], names=["Weekday_Index", "Charging_Hour"])
    tables = {
        "hourly_demand": summarize_groups(data, ["Charging_Hour"], pd.Index(range(24), name="Charging_Hour"), days),
        "daily_demand": summarize_groups(data, ["Charging_Date"], pd.Index(calendar.Charging_Date), 1),
        "weekday_demand": summarize_groups(data, ["Weekday_Index"], pd.Index(range(7), name="Weekday_Index"), weekday_days.to_numpy()),
        "weekday_weekend_demand": summarize_groups(data, ["Day_Type"], pd.Index(["Weekday", "Weekend"], name="Day_Type"), type_days.to_numpy()),
        "day_hour_demand": summarize_groups(data, ["Weekday_Index", "Charging_Hour"], day_hour, weekday_days.reindex(day_hour.get_level_values(0)).to_numpy()),
        "monthly_demand": summarize_groups(data, ["Year_Month"], months.index, months.to_numpy()),
    }
    for name in ["weekday_demand", "day_hour_demand"]:
        tables[name].insert(1, "Weekday_Name", tables[name].Weekday_Index.map(dict(enumerate(WEEKDAYS))))
    hourly = tables["hourly_demand"]
    hourly["relative_demand_index"] = hourly.avg_sessions_per_day / hourly.avg_sessions_per_day.mean()
    monthly = tables["monthly_demand"]
    month_lengths = calendar.groupby("Year_Month").Days_In_Month.first()
    monthly["is_partial_boundary_month"] = monthly.calendar_days.lt(month_lengths.to_numpy())
    return tables


def monthly_sensitivity(data, monthly):
    """Compare baseline energy with the union-of-plausibility-flags exclusion scenario."""
    result = monthly[["Year_Month", "calendar_days", "is_partial_boundary_month", "session_count",
                      "valid_energy_session_count", "invalid_energy_session_count", "total_recorded_energy_kwh"]].copy()
    grouped = data.groupby("Year_Month")
    excluded = data.Sensitivity_Excluded
    result["excluded_session_count"] = grouped.Sensitivity_Excluded.sum().reindex(result.Year_Month, fill_value=0).to_numpy()
    result["retained_session_count"] = result.session_count - result.excluded_session_count
    for label, mask in [("retained", ~excluded), ("excluded", excluded)]:
        subset = data.loc[mask]
        subset_groups = subset.groupby("Year_Month")
        result[label + "_valid_energy_session_count"] = subset_groups.Valid_Energy.sum().reindex(result.Year_Month, fill_value=0).to_numpy()
        result[label + "_recorded_energy_kwh"] = subset_groups.Recorded_Energy_kWh.sum(min_count=1).reindex(result.Year_Month).to_numpy()
        result[label + "_energy_observed_dates"] = subset.loc[subset.Valid_Energy].groupby("Year_Month").Charging_Date.nunique().reindex(result.Year_Month, fill_value=0).to_numpy()
    result["retained_valid_energy_fraction"] = result.retained_valid_energy_session_count / result.valid_energy_session_count.replace(0, float("nan"))
    result["retained_avg_recorded_energy_per_calendar_day_kwh"] = result.retained_recorded_energy_kwh / result.calendar_days
    result["scenario"] = "Sensitivity only: exclude union of true plausibility flags; demand unchanged"
    return result



def location_hourly_profile(data):
    """Percentages are conditional on each location type, with all 24 hours retained."""
    index = pd.MultiIndex.from_product([LOCATION_TYPES, range(24)], names=["Location_Type", "Charging_Hour"])
    counts = data.groupby(["Location_Type", "Charging_Hour"]).size().reindex(index, fill_value=0)
    result = counts.rename("session_count").reset_index()
    totals = data.groupby("Location_Type").size()
    result["location_session_count"] = result.Location_Type.map(totals).fillna(0).astype("int64")
    result["session_percentage"] = result.session_count / result.location_session_count.replace(0, float("nan")) * 100
    return result


def weekday_variability(daily, calendar):
    """Use the existing complete daily calendar, never just dates having sessions."""
    observations = daily[["Charging_Date", "session_count"]].merge(
        calendar[["Charging_Date", "Weekday_Index"]], on="Charging_Date", validate="one_to_one")
    observations["Weekday_Name"] = observations.Weekday_Index.map(dict(enumerate(WEEKDAYS)))
    grouped = observations.groupby("Weekday_Index").session_count
    result = grouped.agg(represented_days="size", session_count="sum", median_sessions="median").reindex(range(7))
    result["q1_sessions"] = grouped.quantile(0.25).reindex(range(7))
    result["q3_sessions"] = grouped.quantile(0.75).reindex(range(7))
    for column in ["represented_days", "session_count"]:
        result[column] = result[column].fillna(0).astype("int64")
    result = result.reset_index()
    result.insert(1, "Weekday_Name", WEEKDAYS)
    return observations, result


def grouped_energy_statistics(data, key, categories):
    """Shared energy count, total, mean and median calculations for new comparisons."""
    grouped = data.groupby(key, sort=False)
    result = grouped.agg(session_count=("Session_ID", "size"),
                         valid_energy_session_count=("Valid_Energy", "sum"),
                         mean_energy_kwh=("Recorded_Energy_kWh", "mean"),
                         median_energy_kwh=("Recorded_Energy_kWh", "median"))
    result["total_recorded_energy_kwh"] = grouped.Recorded_Energy_kWh.sum(min_count=1)
    result = result.reindex(pd.Index(categories, name=key))
    for column in ["session_count", "valid_energy_session_count"]:
        result[column] = result[column].fillna(0).astype("int64")
    result["invalid_energy_session_count"] = result.session_count - result.valid_energy_session_count
    return result.reset_index()


def time_period_energy(data):
    """Half-open hour bins cover every start; unequal lengths do not affect per-session means."""
    periods = pd.cut(data.Charging_Hour, bins=PERIOD_BOUNDARIES, labels=TIME_PERIODS, right=False)
    result = grouped_energy_statistics(data.assign(Time_Period=periods.astype("string")), "Time_Period", TIME_PERIODS)
    result.insert(1, "start_hour_inclusive", PERIOD_BOUNDARIES[:-1])
    result.insert(2, "end_hour_exclusive", PERIOD_BOUNDARIES[1:])
    return result


def charger_type_comparison(data):
    """Separate delivered energy, active charging time and connected occupancy."""
    result = grouped_energy_statistics(data, "Charger_Type", CHARGER_TYPES).set_index("Charger_Type")
    grouped = data.groupby("Charger_Type")
    for source, label in [("Active_Duration_Min", "active_charging_duration"),
                          ("Connected_Duration_Min", "connected_duration")]:
        result["valid_" + label + "_session_count"] = grouped[source].count().reindex(CHARGER_TYPES, fill_value=0)
        result["mean_" + label + "_min"] = grouped[source].mean().reindex(CHARGER_TYPES)
        result["median_" + label + "_min"] = grouped[source].median().reindex(CHARGER_TYPES)
    for supplied in ["Active_Charging_Duration_Min", "Session_Duration_Min"]:
        result[supplied + "_mismatch_count"] = grouped[supplied + "_Mismatch"].sum().reindex(CHARGER_TYPES, fill_value=0)
    return result.reset_index()


def sensitivity_has_variation(table):
    """A comparison needs both retained and excluded valid-energy observations."""
    return bool(table.excluded_valid_energy_session_count.sum() > 0 and table.retained_valid_energy_session_count.sum() > 0)


def additional_analyses(data, daily, calendar):
    """Build and reconcile the four additional analyses and daily boxplot observations."""
    observations, variability = weekday_variability(daily, calendar)
    tables = {"location_type_hourly": location_hourly_profile(data),
              "daily_weekday_counts": observations, "weekday_variability": variability,
              "time_period_energy": time_period_energy(data),
              "charger_type_comparison": charger_type_comparison(data)}
    checks = {name + "_session_count": int(table.session_count.sum()) == len(data) for name, table in tables.items()}
    percentages = tables["location_type_hourly"].groupby("Location_Type").session_percentage.sum(min_count=1)
    present = data.Location_Type.unique()
    checks["location_percentages"] = bool(percentages.loc[present].sub(100).abs().lt(1e-8).all())
    checks["complete_calendar"] = observations.Charging_Date.tolist() == calendar.Charging_Date.tolist()
    checks["weekday_denominators"] = int(variability.represented_days.sum()) == len(calendar)
    expected_energy = data.Recorded_Energy_kWh.sum(min_count=1)
    for name in ["time_period_energy", "charger_type_comparison"]:
        table = tables[name]
        total = table.total_recorded_energy_kwh.sum(min_count=1)
        checks[name + "_valid_energy_count"] = int(table.valid_energy_session_count.sum()) == int(data.Valid_Energy.sum())
        checks[name + "_energy_total"] = bool((pd.isna(total) and pd.isna(expected_energy)) or math.isclose(total, expected_energy, rel_tol=1e-10, abs_tol=1e-6))
    if not all(checks.values()):
        raise ValueError("Additional-analysis reconciliation failed.")
    return tables, checks


def reconcile_tables(data, calendar, tables, sensitivity):
    """Fail on count, energy, dimension, ordering or sensitivity reconciliation errors."""
    expected_count = len(data)
    expected_valid = int(data.Valid_Energy.sum())
    expected_energy = data.Recorded_Energy_kWh.sum(min_count=1)
    results = {}
    for name, table in tables.items():
        total = table.total_recorded_energy_kwh.sum(min_count=1)
        energy_ok = (pd.isna(total) and pd.isna(expected_energy)) or (
            pd.notna(total) and pd.notna(expected_energy)
            and math.isfinite(total) and math.isfinite(expected_energy)
            and math.isclose(total, expected_energy, rel_tol=1e-10, abs_tol=1e-6))
        checks = {
            "session_count": int(table.session_count.sum()) == expected_count,
            "valid_energy_count": int(table.valid_energy_session_count.sum()) == expected_valid,
            "invalid_energy_count": int(table.invalid_energy_session_count.sum()) == expected_count - expected_valid,
            "energy_total": bool(energy_ok),
            "row_count_partition": bool((table.session_count == table.valid_energy_session_count + table.invalid_energy_session_count).all()),
        }
        results[name] = checks
    dimensions = {
        "hourly": tables["hourly_demand"].Charging_Hour.tolist() == list(range(24)),
        "daily": tables["daily_demand"].Charging_Date.tolist() == calendar.Charging_Date.tolist(),
        "weekday": tables["weekday_demand"].Weekday_Index.tolist() == list(range(7)),
        "weekday_weekend": tables["weekday_weekend_demand"].Day_Type.tolist() == ["Weekday", "Weekend"],
        "day_hour": list(tables["day_hour_demand"][["Weekday_Index", "Charging_Hour"]].itertuples(index=False, name=None)) == [(day, hour) for day in range(7) for hour in range(24)],
        "monthly": tables["monthly_demand"].Year_Month.tolist() == sorted(calendar.Year_Month.unique()),
    }
    sensitivity_checks = {
        "demand_unchanged": sensitivity.session_count.tolist() == tables["monthly_demand"].session_count.tolist(),
        "row_partition": bool((sensitivity.retained_session_count + sensitivity.excluded_session_count == sensitivity.session_count).all()),
        "valid_energy_partition": bool((sensitivity.retained_valid_energy_session_count + sensitivity.excluded_valid_energy_session_count == sensitivity.valid_energy_session_count).all()),
        "energy_partition": bool(((sensitivity.retained_recorded_energy_kwh.fillna(0) + sensitivity.excluded_recorded_energy_kwh.fillna(0) - sensitivity.total_recorded_energy_kwh.fillna(0)).abs() <= (1e-6 + sensitivity.total_recorded_energy_kwh.fillna(0).abs() * 1e-10)).all()),
    }
    if not all(all(checks.values()) for checks in [*results.values(), dimensions, sensitivity_checks]):
        raise ValueError("Analysis reconciliation failed; no outputs should be used.")
    return {"tables": results, "dimensions_and_ordering": dimensions, "sensitivity": sensitivity_checks, "all_passed": True}


def period_extremes(table, keys):
    """Return all tied busiest/lowest periods using average sessions per represented day."""
    values = table.avg_sessions_per_day
    return {label: {"avg_sessions_per_day": float(value),
                    "periods": table.loc[values.eq(value), keys].to_dict(orient="records")}
            for label, value in [("busiest", values.max()), ("lowest", values.min())]}


def analyze_sessions(raw):
    """Calculate tables and an aggregate-only summary, without modifying source data."""
    data, validation = validate_sessions(raw)
    calendar = build_calendar(data.Session_Start)
    tables = build_demand_tables(data, calendar)
    sensitivity = monthly_sensitivity(data, tables["monthly_demand"])
    reconciliation = reconcile_tables(data, calendar, tables, sensitivity)
    keys = {"hourly_demand": ["Charging_Hour"], "daily_demand": ["Charging_Date"],
            "weekday_demand": ["Weekday_Index", "Weekday_Name"], "weekday_weekend_demand": ["Day_Type"],
            "day_hour_demand": ["Weekday_Index", "Weekday_Name", "Charging_Hour"], "monthly_demand": ["Year_Month"]}
    total_energy = data.Recorded_Energy_kWh.sum(min_count=1)
    summary = {
        "coverage": coverage_summary(data.Session_Start), "input_session_count": len(data),
        "valid_energy_session_count": int(data.Valid_Energy.sum()),
        "invalid_energy_session_count": int((~data.Valid_Energy).sum()),
        "total_recorded_energy_kwh": total_energy,
        "avg_sessions_per_day": len(data) / len(calendar),
        "avg_recorded_energy_per_valid_session_kwh": total_energy / int(data.Valid_Energy.sum()) if data.Valid_Energy.any() else None,
        "avg_recorded_energy_per_day_kwh": total_energy / len(calendar),
        "input_validation": validation,
        "output_row_counts": {**{name: len(table) for name, table in tables.items()}, "monthly_energy_sensitivity": len(sensitivity)},
        "period_extremes_metric": "avg_sessions_per_day; all exact ties among categories with represented dates, including zero-demand categories",
        "empty_group_policy": "Session counts are zero for absent categories. Demand averages are zero when calendar_days > 0, undefined when calendar_days = 0. Energy totals/averages are missing without valid energy observations; energy_observation_status distinguishes no_sessions from no_valid_energy.",
        "period_extremes": {name: period_extremes(table, keys[name]) for name, table in tables.items()},
        "hourly_relative_demand_index": {"definition": "Hourly average sessions/day divided by mean of all 24 hourly averages; project-defined relative session-start indicator.",
                                         "minimum": tables["hourly_demand"].relative_demand_index.min(),
                                         "maximum": tables["hourly_demand"].relative_demand_index.max()},
        "partial_boundary_months": tables["monthly_demand"].loc[tables["monthly_demand"].is_partial_boundary_month, "Year_Month"].tolist(),
        "sensitivity": {"excluded_session_count": int(data.Sensitivity_Excluded.sum()),
                        "retained_session_count": int((~data.Sensitivity_Excluded).sum()),
                        "retained_valid_energy_session_count": int((~data.Sensitivity_Excluded & data.Valid_Energy).sum()),
                        "retained_recorded_energy_kwh": data.loc[~data.Sensitivity_Excluded, "Recorded_Energy_kWh"].sum(min_count=1),
                        "excluded_recorded_energy_kwh": data.loc[data.Sensitivity_Excluded, "Recorded_Energy_kWh"].sum(min_count=1)},
        "reconciliation": reconciliation, "limitations": LIMITATIONS,
    }
    tables["monthly_energy_sensitivity"] = sensitivity
    extra, checks = additional_analyses(data, tables["daily_demand"], calendar)
    tables.update(extra)
    summary["additional_reconciliation"] = checks
    summary["output_row_counts"] = {name: len(table) for name, table in tables.items()}
    summary["sensitivity"]["comparison_informative"] = sensitivity_has_variation(sensitivity)
    summary["additional_methods"] = {
        "location_percentage": "100 * location-hour starts / all starts for that location type. Empty location categories have undefined percentages.",
        "weekday_variability": "Daily counts on the complete calendar; pandas linear quartiles; boxplots use 1.5 IQR whiskers.",
        "periods": dict(zip(TIME_PERIODS, ["[00,06)", "[06,12)", "[12,17)", "[17,22)", "[22,24)"])),
        "energy_attribution": "Whole-session valid energy assigned to its start period; per-session averages, not hourly electricity load.",
        "durations": "Active = Charging_End - Session_Start; connected = Session_End - Session_Start. Finite supplied minute fields compared with 0.01 minute tolerance.",
        "synthetic": "Location categories and separate active/connected intervals are documented simulation contracts; generator hour weights/distributions were not supplied, so observed patterns are not asserted as generator probabilities or real behavior.",
    }
    return tables, summary


def json_safe(value):
    """Convert pandas/numpy scalars and undefined/nonfinite numbers to strict JSON."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        value = value.item()
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def run_analysis(input_path, output_dir, raw_path=None):
    """Read the cleaned CSV, export summaries, and verify supplied source hashes."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    sources = {"cleaned": input_path}
    if raw_path is not None:
        sources["raw"] = Path(raw_path)
    before = {name: file_hash(path) for name, path in sources.items()}
    raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    tables, summary = analyze_sessions(raw)
    destinations = [output_dir / (name + ".csv") for name in tables] + [output_dir / "analysis_summary.json"]
    if any(path.resolve() == source.resolve() for path in destinations for source in sources.values()):
        raise ValueError("An output would overwrite an input file; choose a different output directory.")
    after = {name: file_hash(path) for name, path in sources.items()}
    if before != after:
        raise ValueError("An input changed during analysis; no outputs written.")
    summary["source_integrity"] = {name: {"sha256_before": before[name], "sha256_after": after[name], "unchanged": True} for name in sources}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(output_dir / (name + ".csv"), index=False)
    if {name: file_hash(path) for name, path in sources.items()} != before:
        raise ValueError("An input changed during export; outputs must not be used.")
    summary = json_safe(summary)
    (output_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return summary


def main():
    """CLI with repository-relative defaults and clear validation failures."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data/processed/charging_sessions.csv")
    parser.add_argument("--output-dir", type=Path, default=root / "outputs/demand")
    parser.add_argument("--raw-input", type=Path, help="Optional raw CSV to fingerprint; default uses the repository raw CSV if present.")
    args = parser.parse_args()
    raw_path = args.raw_input or (DEFAULT_INPUT if DEFAULT_INPUT.is_file() else None)
    try:
        summary = run_analysis(args.input, args.output_dir, raw_path)
    except (OSError, ValueError, pd.errors.ParserError) as error:
        parser.exit(1, f"Demand analysis failed: {error}\n")
    print(json.dumps({key: summary[key] for key in ["input_session_count", "valid_energy_session_count", "total_recorded_energy_kwh", "reconciliation"]}, indent=2))


if __name__ == "__main__":
    main()

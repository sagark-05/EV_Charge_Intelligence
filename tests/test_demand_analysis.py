import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.data_preparation import file_hash, numeric_status
from src.demand_analysis import (
    FLAGS, analyze_sessions, build_calendar, json_safe, parse_boolean_flags,
    reconcile_tables, run_analysis, validate_sessions,
)


def sessions(dates, energies=None, flags=None):
    """Small cleaned-export fixture with documented energy status/boolean text."""
    energies = ["10"] * len(dates) if energies is None else energies
    frame = pd.DataFrame({
        "Session_ID": [f"S{i}" for i in range(len(dates))],
        "Session_Start": dates, "Energy_Delivered_kWh": energies,
        FLAGS[0]: ["False"] * len(dates), FLAGS[1]: ["False"] * len(dates),
    })
    frame["Energy_Delivered_kWh_Validity"] = numeric_status(frame.Energy_Delivered_kWh)[1]
    if flags:
        for column, values in flags.items():
            frame[column] = values
    return frame


def test_unequal_weekday_weekend_and_hour_denominators():
    # Friday through following Monday: 2 Fridays, 2 Mondays, 7 weekdays, 4 weekend dates.
    raw = sessions(["05-01-2024 08:00", "06-01-2024 08:00", "15-01-2024 08:00"])
    tables, report = analyze_sessions(raw)
    types = tables["weekday_weekend_demand"].set_index("Day_Type")
    assert types.loc["Weekday", "calendar_days"] == 7
    assert types.loc["Weekend", "calendar_days"] == 4
    assert types.loc["Weekday", "avg_sessions_per_day"] == pytest.approx(2 / 7)
    assert types.loc["Weekend", "avg_sessions_per_day"] == pytest.approx(1 / 4)
    weekday = tables["weekday_demand"].set_index("Weekday_Name")
    assert weekday.loc["Monday", "calendar_days"] == 2
    assert weekday.loc["Friday", "avg_sessions_per_day"] == 0.5
    heatmap = tables["day_hour_demand"].set_index(["Weekday_Name", "Charging_Hour"])
    assert heatmap.loc[("Friday", 8), "calendar_days"] == 2
    assert heatmap.loc[("Friday", 8), "avg_sessions_per_day"] == 0.5
    assert tables["hourly_demand"].iloc[8].calendar_days == 11
    assert report["reconciliation"]["all_passed"]


def test_zero_session_dates_absent_categories_and_missing_energy():
    tables, summary = analyze_sessions(sessions(["01-01-2024 12:00", "03-01-2024 12:00"], ["0", "bad"]))
    daily = tables["daily_demand"].set_index("Charging_Date")
    assert daily.index.tolist() == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert daily.loc["2024-01-01", "total_recorded_energy_kwh"] == 0
    assert daily.loc["2024-01-01", "energy_observation_status"] == "valid_energy_observed"
    assert daily.loc["2024-01-02", "session_count"] == 0
    assert daily.loc["2024-01-02", "avg_sessions_per_day"] == 0
    assert daily.loc["2024-01-02", "energy_observation_status"] == "no_sessions"
    assert pd.isna(daily.loc["2024-01-02", "total_recorded_energy_kwh"])
    assert daily.loc["2024-01-03", "energy_observation_status"] == "no_valid_energy"
    assert pd.isna(daily.loc["2024-01-03", "total_recorded_energy_kwh"])
    hourly = tables["hourly_demand"]
    assert hourly.Charging_Hour.tolist() == list(range(24))
    assert hourly.iloc[0].session_count == 0
    assert len(tables["day_hour_demand"]) == 168
    assert tables["weekday_demand"].Weekday_Name.tolist() == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert summary["period_extremes"]["hourly_demand"]["lowest"]["periods"] == [{"Charging_Hour": h} for h in range(24) if h != 12]


def test_leap_day_cross_year_and_partial_months():
    tables, summary = analyze_sessions(sessions(["31-12-2023 23:59", "01-03-2024 00:00"]))
    monthly = tables["monthly_demand"].set_index("Year_Month")
    assert monthly.index.tolist() == ["2023-12", "2024-01", "2024-02", "2024-03"]
    assert monthly.calendar_days.tolist() == [1, 31, 29, 1]
    assert monthly.is_partial_boundary_month.tolist() == [True, False, False, True]
    assert "2024-02-29" in tables["daily_demand"].Charging_Date.tolist()
    assert summary["coverage"]["inclusive_calendar_days"] == 62
    assert summary["partial_boundary_months"] == ["2023-12", "2024-03"]


def test_zero_invalid_energy_and_declared_status_mismatches():
    values = ["0", "", "NaN", "inf", "-1", "text", "2.5"]
    frame = sessions(["01-01-2024 00:00"] * len(values), values)
    # Revalidation must not trust a stale declaration and must preserve demand.
    frame.loc[1, "Energy_Delivered_kWh_Validity"] = "valid"
    tables, summary = analyze_sessions(frame)
    assert summary["input_session_count"] == 7
    assert summary["valid_energy_session_count"] == 2
    assert summary["invalid_energy_session_count"] == 5
    assert summary["input_validation"]["declared_energy_validity_mismatch_count"] == 1
    assert summary["input_validation"]["energy_validity_counts"] == {
        "valid": 2, "missing": 1, "nonfinite": 2, "negative": 1, "nonnumeric": 1}
    assert summary["total_recorded_energy_kwh"] == 2.5
    for table in [tables[key] for key in tables if key != "monthly_energy_sensitivity"]:
        assert table.session_count.sum() == 7
        assert table.valid_energy_session_count.sum() == 2
        assert table.invalid_energy_session_count.sum() == 5
        assert table.total_recorded_energy_kwh.sum(min_count=1) == 2.5
    hourly = tables["hourly_demand"].iloc[0]
    assert hourly.avg_recorded_energy_per_valid_session_kwh == 1.25


def test_explicit_string_booleans_union_overlap_and_sensitivity():
    frame = sessions(["01-01-2024 01:00"] * 4, ["10", "20", "30", "40"],
                     {FLAGS[0]: ["False", "True", "True", ""], FLAGS[1]: ["False", "False", "True", "False"]})
    tables, summary = analyze_sessions(frame)
    sensitivity = tables["monthly_energy_sensitivity"].iloc[0]
    assert summary["input_validation"]["plausibility_union_count"] == 2
    assert summary["input_validation"]["overlapping_flags_count"] == 1
    assert sensitivity.session_count == 4
    assert sensitivity.retained_session_count == 2
    assert sensitivity.excluded_session_count == 2
    assert sensitivity.retained_recorded_energy_kwh == 50
    assert sensitivity.excluded_recorded_energy_kwh == 50
    assert sensitivity.total_recorded_energy_kwh == 100
    assert sensitivity.retained_valid_energy_fraction == 0.5
    assert sensitivity.retained_energy_observed_dates == 1
    assert summary["input_validation"]["plausibility_flags"][FLAGS[0]]["not_evaluable"] == 1
    assert parse_boolean_flags(pd.Series(["False", "True", "", None]), "flag").tolist()[:2] == [False, True]


def test_busiest_ties_and_recomputed_features():
    frame = sessions(["01-01-2024 08:00", "02-01-2024 09:00"])
    frame["Charging_Hour"] = "99"
    frame["Is_Weekend"] = "False"
    tables, summary = analyze_sessions(frame)
    assert summary["period_extremes"]["hourly_demand"]["busiest"]["periods"] == [{"Charging_Hour": 8}, {"Charging_Hour": 9}]
    assert len(summary["period_extremes"]["daily_demand"]["busiest"]["periods"]) == 2
    assert tables["hourly_demand"].relative_demand_index.max() == pytest.approx(12)
    assert tables["weekday_weekend_demand"].session_count.tolist() == [2, 0]
    assert frame.Charging_Hour.tolist() == ["99", "99"]


@pytest.mark.parametrize("mutation,match", [
    (lambda f: f.iloc[:0], "at least one"),
    (lambda f: f.drop(columns=FLAGS[0]), "Missing required columns"),
    (lambda f: f.assign(Session_ID=" "), "nonblank"),
    (lambda f: pd.concat([f, f]), "unique"),
    (lambda f: f.assign(Session_Start="2024-01-01 01:00"), "DD-MM-YYYY"),
    (lambda f: f.assign(Session_Start="31-02-2024 01:00"), "invalid timestamps"),
    (lambda f: f.assign(Energy_Delivered_kWh_Validity="unknown"), "undocumented status"),
    (lambda f: f.assign(**{FLAGS[1]: "0"}), "invalid boolean"),
])
def test_malformed_inputs(mutation, match):
    with pytest.raises(ValueError, match=match):
        analyze_sessions(mutation(sessions(["01-01-2024 01:00"])))


def test_no_valid_energy_strict_json_and_deterministic_exports(tmp_path):
    source = tmp_path / "cleaned.csv"
    raw = tmp_path / "raw.csv"
    frame = sessions(["01-01-2024 01:00", "03-01-2024 02:00"], ["", "NaN"])
    frame.to_csv(source, index=False)
    raw.write_text("original raw source\n")
    before = (file_hash(source), file_hash(raw))
    output = tmp_path / "out"
    summary = run_analysis(source, output, raw)
    assert summary["total_recorded_energy_kwh"] is None
    assert summary["avg_recorded_energy_per_day_kwh"] is None
    assert summary["reconciliation"]["all_passed"]
    assert len(list(output.glob("*.csv"))) == 7
    outputs = {p.name: p.read_bytes() for p in output.iterdir()}
    run_analysis(source, output, raw)
    assert outputs == {p.name: p.read_bytes() for p in output.iterdir()}
    assert before == (file_hash(source), file_hash(raw))
    json.loads((output / "analysis_summary.json").read_text(), parse_constant=lambda s: pytest.fail(s))
    assert json_safe({"a": float("inf"), "b": float("nan")}) == {"a": None, "b": None}


def test_cli_empty_file_fails_clearly(tmp_path):
    source = tmp_path / "empty.csv"
    source.write_text("")
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / "src/demand_analysis.py"),
               "--input", str(source), "--output-dir", str(tmp_path / "out")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert "Demand analysis failed:" in result.stderr
    assert not (tmp_path / "out").exists()



def test_unrepresented_weekdays_have_zero_counts_but_undefined_rates():
    tables, summary = analyze_sessions(sessions(["01-01-2024 01:00"]))
    weekday = tables["weekday_demand"].set_index("Weekday_Index")
    assert weekday.loc[1, "session_count"] == 0
    assert weekday.loc[1, "calendar_days"] == 0
    assert pd.isna(weekday.loc[1, "avg_sessions_per_day"])
    assert summary["period_extremes"]["weekday_demand"]["lowest"]["periods"] == [{"Weekday_Index": 0, "Weekday_Name": "Monday"}]


def test_all_plausibility_exclusions_keep_demand_and_missing_retained_energy():
    frame = sessions(["01-01-2024 00:00"], ["0"], {FLAGS[0]: ["True"]})
    tables, summary = analyze_sessions(frame)
    result = tables["monthly_energy_sensitivity"].iloc[0]
    assert result.session_count == result.excluded_session_count == 1
    assert result.retained_session_count == 0
    assert result.excluded_recorded_energy_kwh == 0
    assert pd.isna(result.retained_recorded_energy_kwh)
    assert summary["valid_energy_session_count"] == 1


@pytest.mark.parametrize("column", ["session_count", "valid_energy_session_count", "total_recorded_energy_kwh"])
def test_reconciliation_detects_independent_count_or_energy_corruption(column):
    frame = sessions(["01-01-2024 00:00", "03-01-2024 00:00"], ["0.1", "0.2"])
    data, _ = validate_sessions(frame)
    tables, _ = analyze_sessions(frame)
    sensitivity = tables.pop("monthly_energy_sensitivity")
    tables["hourly_demand"].loc[0, column] += 1
    with pytest.raises(ValueError, match="reconciliation failed"):
        reconcile_tables(data, build_calendar(data.Session_Start), tables, sensitivity)

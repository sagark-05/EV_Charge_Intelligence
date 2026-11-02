import json

import pandas as pd
import pytest

from src.data_preparation import file_hash, parse_timestamp, prepare_data, run_pipeline


@pytest.fixture
def session():
    return {"Session_ID": "S1", "Session_Start": "06-03-2024 03:40",
            "Session_End": "06-03-2024 04:28", "Session_Duration_Min": "48",
            "Day_of_Week": "Wednesday", "Month": "3", "Station_ID": "ST1",
            "Station_Name": "Station One", "City": "Kochi", "State": "Kerala",
            "Energy_Delivered_kWh": "10", "Queue_Time_Min": "0",
            "Vehicle_Battery_kWh": "60", "Charger_Power_kW": "50"}


def test_explicit_day_first_and_strict_shape():
    result = parse_timestamp(pd.Series(["06-03-2024 03:40", "03-06-2024 03:40",
                                       "2024-03-06 03:40", "31-02-2024 03:40",
                                       "6-03-2024 03:40", "", "06-03-2024 24:00"]))
    assert result.iloc[0].month == 3
    assert result.iloc[1].month == 6
    assert result.iloc[2:].isna().all()


def test_duplicates_conflicts_and_reconciliation(session):
    records = [session, session.copy(), dict(session, City="Delhi"),
               dict(session, Session_ID="S2"), dict(session, Session_ID=" "),
               dict(session, Session_ID="S3", Session_Start="bad"),
               dict(session, Session_ID="S4", Session_End="06-03-2024 02:00")]
    accepted, rejected, flagged, report = prepare_data(pd.DataFrame(records))
    assert accepted.Session_ID.tolist() == ["S2"]
    assert rejected.Source_Row_Number.tolist() == [2, 4, 6, 7, 8]
    assert rejected.Session_ID.eq("S1").sum() == 2
    assert rejected.Quality_Reasons.str.contains("conflicting_session_id").sum() == 2
    assert report["reconciliation"] == {"input_rows": 7, "exact_duplicates_removed": 1,
                                        "rejected_rows": 5, "accepted_rows": 1, "balanced": True}
    assert "missing_session_id" in rejected.iloc[2].Quality_Reasons
    assert "invalid_session_start" in rejected.iloc[3].Quality_Reasons
    assert "end_before_start" in rejected.iloc[4].Quality_Reasons
    assert len(flagged) == 6


def test_flags_do_not_correct_or_reject(session):
    row = dict(session, Session_Duration_Min="99", Day_of_Week="Monday", Month="4", City="")
    accepted, rejected, flagged, report = prepare_data(pd.DataFrame([row]))
    assert len(accepted) == 1 and rejected.empty
    assert accepted.iloc[0].Session_Duration_Min == "99"
    assert accepted.iloc[0].City == ""
    assert set(flagged.iloc[0].Quality_Reasons.split(";")) == {
        "duration_mismatch", "weekday_mismatch", "month_mismatch", "missing_value:City"}


def test_exports_integrity_and_repeatability(tmp_path, session):
    source = tmp_path / "raw.csv"
    pd.DataFrame([session, dict(session, Session_ID="S2", Session_End="bad")]).to_csv(source, index=False)
    before = file_hash(source)
    report = run_pipeline(source, tmp_path / "processed", tmp_path / "quality")
    paths = [tmp_path / "processed/charging_sessions.csv", tmp_path / "processed/rejected_sessions.csv",
             tmp_path / "quality/flagged_records.csv", tmp_path / "quality/quality_report.json"]
    output = {path: path.read_bytes() for path in paths}
    run_pipeline(source, tmp_path / "processed", tmp_path / "quality")
    assert output == {path: path.read_bytes() for path in paths}
    assert file_hash(source) == before == report["source_integrity"]["sha256_after"]
    assert report["reconciliation"]["balanced"]
    assert "S1" not in json.dumps(report)
    assert pd.read_csv(tmp_path / "processed/charging_sessions.csv").Session_Start.iloc[0] == session["Session_Start"]
    assert "invalid_session_end" in pd.read_csv(tmp_path / "processed/rejected_sessions.csv").Quality_Reasons.iloc[0]


def test_missing_schema_has_helpful_error():
    with pytest.raises(ValueError, match="Missing required columns"):
        prepare_data(pd.DataFrame({"Session_ID": ["S1"]}))


def test_station_conflicts_flag_every_affected_row(session):
    rows = [session, dict(session, Session_ID="S2", Station_Name="Other", City="Delhi", State="Delhi")]
    accepted, rejected, flagged, report = prepare_data(pd.DataFrame(rows))
    assert len(accepted) == 2 and rejected.empty
    assert report["station_ids_with_multiple_values"] == {"Station_Name": 1, "City": 1, "State": 1}
    assert flagged.Quality_Reasons.str.contains("station_multiple:State").all()


@pytest.mark.parametrize("start,end,date,hour,index,name,weekend,month,minutes", [
    ("31-12-2023 23:30", "01-01-2024 00:30", "2023-12-31", 23, 6, "Sunday", True, "2023-12", 60),
    ("01-01-2024 00:00", "02-01-2024 01:00", "2024-01-01", 0, 0, "Monday", False, "2024-01", 1500),
    ("06-01-2024 00:00", "06-01-2024 00:00", "2024-01-06", 0, 5, "Saturday", True, "2024-01", 0),
])
def test_derived_boundaries(session, start, end, date, hour, index, name, weekend, month, minutes):
    row = dict(session, Session_Start=start, Session_End=end, Charging_Date="stale", Charging_Hour="99")
    accepted, _, _, report = prepare_data(pd.DataFrame([row]))
    result = accepted.iloc[0]
    assert result.Charging_Date == date
    assert result.Charging_Hour == hour
    assert result.Weekday_Index == index
    assert result.Weekday_Name == name
    assert bool(result.Is_Weekend) == weekend
    assert result.Year_Month == month
    assert result.Calculated_Session_Duration_Min == minutes
    assert result.Session_Start == start and result.Session_End == end
    assert report["existing_derived_columns_recomputed"] == ["Charging_Date", "Charging_Hour"]


@pytest.mark.parametrize("value,status", [
    ("0", "valid"), ("2.5", "valid"), ("", "missing"), ("  ", "missing"),
    (None, "missing"), (float("nan"), "missing"), ("text", "nonnumeric"),
    ("-1", "negative"), ("NaN", "nonfinite"), ("inf", "nonfinite"),
    ("-Infinity", "nonfinite"), (float("inf"), "nonfinite"),
])
def test_measurement_validity_preserves_demand(session, value, status):
    row = dict(session, Energy_Delivered_kWh=value, Queue_Time_Min=value)
    accepted, rejected, flagged, report = prepare_data(pd.DataFrame([row]))
    assert len(accepted) == 1 and rejected.empty
    for column in ["Energy_Delivered_kWh", "Queue_Time_Min"]:
        assert accepted.iloc[0][column + "_Validity"] == status
        assert report["measurement_validity"][column]["accepted"][status] == 1
        if status != "valid":
            assert column + ":" + status in flagged.iloc[0].Quality_Reasons
    assert report["reconciliation"]["balanced"]


def test_plausibility_is_separate_from_validity(session):
    rows = [dict(session, Energy_Delivered_kWh="100"),
            dict(session, Session_ID="S2", Energy_Delivered_kWh="10", Vehicle_Battery_kWh="bad", Charger_Power_kW="inf"),
            dict(session, Session_ID="S3", Energy_Delivered_kWh="0", Vehicle_Battery_kWh="0", Charger_Power_kW="0")]
    accepted, rejected, flagged, report = prepare_data(pd.DataFrame(rows))
    assert len(accepted) == 3 and rejected.empty
    assert accepted.Energy_Delivered_kWh_Validity.eq("valid").all()
    for column in ["Energy_Exceeds_Battery_Capacity", "Energy_Exceeds_Nominal_Charger_Energy"]:
        assert bool(accepted.iloc[0][column])
        assert pd.isna(accepted.iloc[1][column])
        assert not bool(accepted.iloc[2][column])
        assert report["plausibility_concerns"][column]["flagged_accepted"] == 1
    assert "plausibility:" in flagged.iloc[0].Quality_Reasons


def test_coverage_inclusive_dates_and_empty_acceptance(session):
    rows = [dict(session, Session_Start="31-12-2023 23:30", Session_End="01-01-2024 00:30"),
            dict(session, Session_ID="S2", Session_Start="02-01-2024 10:00", Session_End="02-01-2024 11:00")]
    first = prepare_data(pd.DataFrame(rows))
    second = prepare_data(pd.DataFrame(rows))
    pd.testing.assert_frame_equal(first[0], second[0])
    assert first[3] == second[3]
    coverage = first[3]["coverage"]
    assert coverage["inclusive_calendar_days"] == 3
    assert coverage["observed_session_dates"] == 2
    assert coverage["first_date"] == "2023-12-31"
    assert coverage["latest_session_start"] == "02-01-2024 10:00"
    empty = prepare_data(pd.DataFrame([dict(session, Session_ID="")]))[3]["coverage"]
    assert empty["inclusive_calendar_days"] == 0
    assert empty["earliest_session_start"] is None



def test_csv_nonfinite_tokens_remain_distinct_from_blank(tmp_path, session):
    rows = [dict(session, Session_ID=f"S{i}", Energy_Delivered_kWh=value, Queue_Time_Min=value)
            for i, value in enumerate(["", "NaN", "Infinity", "-2", "zero", "0"])]
    source = tmp_path / "raw.csv"
    pd.DataFrame(rows).to_csv(source, index=False)
    report = run_pipeline(source, tmp_path / "processed", tmp_path / "quality")
    assert report["reconciliation"]["accepted_rows"] == 6
    for column in ["Energy_Delivered_kWh", "Queue_Time_Min"]:
        assert report["measurement_validity"][column]["accepted"] == {
            "valid": 1, "missing": 1, "nonnumeric": 1, "nonfinite": 2, "negative": 1}
    accepted = pd.read_csv(tmp_path / "processed/charging_sessions.csv", keep_default_na=False)
    assert accepted.Energy_Delivered_kWh.tolist() == ["", "NaN", "Infinity", "-2", "zero", "0"]


@pytest.mark.parametrize("directory", [".", "notebooks"])
def test_notebook_path_bootstrap(directory, monkeypatch):
    from pathlib import Path
    import nbformat

    root = Path(__file__).resolve().parents[1]
    notebook = nbformat.read(root / "notebooks/01_preprocessing.ipynb", as_version=4)
    bootstrap = next(cell.source for cell in notebook.cells if cell.cell_type == "code")
    monkeypatch.chdir(root / directory)
    namespace = {}
    exec(bootstrap.split("report = run_pipeline")[0], namespace)
    assert namespace["ROOT"] == root
    assert callable(namespace["run_pipeline"])

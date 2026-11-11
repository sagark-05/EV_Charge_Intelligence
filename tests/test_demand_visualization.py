"""Artifact smoke checks; styling is verified by visual inspection."""
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
from PIL import Image
import pytest

from src.data_preparation import file_hash
from src.demand_analysis import run_analysis
from src.demand_visualization import load_analysis


def test_plotting_cli_generates_all_artifacts_without_modifying_summaries(tmp_path):
    source = tmp_path / "sessions.csv"
    pd.DataFrame({
        "Session_ID": ["S1", "S2", "S3"], "Timezone": "Asia/Kolkata",
        "Location_Type": ["Workplace", "Retail", "Highway"],
        "Charger_Type": ["AC Slow", "AC Fast", "DC Fast"],
        "Charging_End": ["31-12-2023 23:30", "01-01-2024 00:30", "08-01-2024 12:30"],
        "Session_End": ["01-01-2024 00:00", "01-01-2024 01:00", "08-01-2024 13:00"],
        "Session_Start": ["31-12-2023 23:00", "01-01-2024 00:00", "08-01-2024 12:00"],
        "Energy_Delivered_kWh": ["0", "", "10"],
        "Energy_Delivered_kWh_Validity": ["valid", "missing", "valid"],
        "Energy_Exceeds_Battery_Capacity": ["False", "", "True"],
        "Energy_Exceeds_Nominal_Charger_Energy": ["False", "", "True"],
    }).to_csv(source, index=False)
    output = tmp_path / "summaries"
    run_analysis(source, output)
    protected = [source, *output.iterdir()]
    before = {p: file_hash(p) for p in protected}
    figures = output / "figures"
    figures.mkdir()
    (figures / "01_hourly_demand.svg").write_text("generated old copy")
    (figures / "user_notes.svg").write_text("preserve user file")
    script = Path(__file__).resolve().parents[1] / "src/demand_visualization.py"
    completed = subprocess.run([sys.executable, str(script), "--input-dir", str(output)],
                               cwd=tmp_path, capture_output=True, text=True,
                               env={**os.environ, "MPLCONFIGDIR": str(tmp_path / "mpl-cache")})
    assert completed.returncode == 0, completed.stderr
    assert "11 charts" in completed.stdout
    figures = output / "figures"
    pngs = sorted(figures.glob("*.png"))
    assert len(pngs) == 11
    assert not (figures / "01_hourly_demand.svg").exists()
    assert (figures / "user_notes.svg").read_text() == "preserve user file"
    for path in pngs:
        with Image.open(path) as image:
            assert min(image.size) > 500
            assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)
            image.verify()
    assert before == {p: file_hash(p) for p in protected}


def test_loader_rejects_unverified_summaries(tmp_path):
    (tmp_path / "analysis_summary.json").write_text('{"reconciliation": {"all_passed": false}}')
    with pytest.raises(ValueError, match="reconciliation must pass"):
        load_analysis(tmp_path)

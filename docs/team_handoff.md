# Team handoff

## Dataset transfer and reproduction

Source status: **generated synthetic Indian charging data**. Generator code, seed, sampling/loss assumptions and reuse licence were not supplied. Timestamp timezone is Asia/Kolkata. Obtain the same CSV directly from the team member through the team's agreed transfer channel and place it at `data/raw/EV_Dataset_India.csv`; GitHub does not contain dataset CSVs. Do not substitute the research paper's dataset. Keep the raw file unchanged.

From the repository root, using Python 3.9 or newer on Linux/macOS:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
sha256sum data/raw/EV_Dataset_India.csv
.venv/bin/python -m pytest -q
.venv/bin/python src/data_preparation.py
.venv/bin/python src/demand_analysis.py
.venv/bin/python src/demand_visualization.py
.venv/bin/python scripts/execute_notebook.py notebooks/01_preprocessing.ipynb
.venv/bin/python scripts/execute_notebook.py notebooks/02_demand_analysis.ipynb
.venv/bin/python scripts/execute_notebook.py notebooks/03_demand_analysis_code_and_charts.ipynb
sha256sum data/raw/EV_Dataset_India.csv data/processed/charging_sessions.csv
```

Expected SHA-256 fingerprints for this handoff:

- Raw (India): `cb67ee7102672b377f168c711ca1d8b76cac48455d3b90ffb17c4f1fba63a069`.
- Cleaned: read `source_integrity.cleaned.sha256_after` in `outputs/demand/analysis_summary.json` after regeneration.

The cleaned hash identifies the current preparation output; different library versions may affect serialization. Compare counts/definitions and investigate any difference rather than silently substituting data. Dependencies use compatible version ranges, not a frozen environment. Jupyter execution needs local kernel sockets. On Windows, use the equivalent virtual-environment Python path; `sha256sum` commands above assume a shell providing that utility.

All CSVs, including aggregate demand exports, are ignored and regenerated locally. Code, tests, docs, executed notebooks, aggregate JSON reports and PNG figures are versioned. Quality reports contain aggregates and hashes, not full session records. Rejected and flagged CSVs remain local audit files; do not add them with `git add -f`.

## Inputs for the remaining modules

**Member 3:** use `data/processed/charging_sessions.csv`, [data dictionary](data_dictionary.md) and `outputs/data_quality/quality_report.json`. `Source_Row_Number` supports audit lookup; local `rejected_sessions.csv` and `flagged_records.csv` carry explicit reasons. Energy/queue `*_Validity` columns distinguish valid, missing, nonnumeric, nonfinite and negative values. Numeric validity requires finite values >= 0; zero is allowed. Use valid measurements for their own metrics without deleting valid demand sessions. The 997 station IDs present have internally consistent mappings; use Area, Location_Type, Port_Count and station-local Port_ID. Synthetic mappings do not validate actual Indian infrastructure. Port overlaps and queue/active/occupancy consistency are checked in preparation.

**Member 4:** use the cleaned session-level CSV and a date table spanning the inclusive represented dates. Preserve IDs and explicitly parse timestamps as `DD-MM-YYYY HH:MM`; use the declared Asia/Kolkata timezone. Derived date/hour/weekday/weekend/year-month fields are provided. Use `outputs/demand/*.csv` and `analysis_summary.json` as fixed reference checks under matching filters. Build interactive measures from session-level data; fixed aggregate averages must not be reused under incompatible filters. Label baseline/sensitivity scenarios and valid-energy coverage separately. Power BI implementation remains future work.

## Validated reference totals and metric rules

- Preparation: 200,000 accepted, zero removed duplicates/rejections/flags or port overlaps.
- Accepted session starts span 01-01-2024 01:53 to 30-12-2025 23:53 in Asia/Kolkata, across 730 inclusive dates. Complete collection including zero-session dates is an assumption; timestamps do not establish uptime or complete boundary-day observation.
- Hourly demand is no longer nearly uniform: relative index 0.10560–2.06376. Hour 09 has the most starts (17,198; 23.56/calendar day), versus hour 01 (880; 1.21/day). This is the generated sample's pattern, not evidence of real congestion or actual Indian charging behavior.
- Weekdays average 277.05 starts/day across 522 dates; weekends average 266.25 across 208 dates. Wednesday is highest (280.02/day); Saturday is lowest (265.68/day). Comparisons use each group's calendar denominator; no significance or causes are inferred.
- All 200,000 energy measurements are numerically valid: 3,014,172.81 kWh total, 15.07 kWh per valid-energy session. Monthly energy/day ranges from 3,327.97 kWh in 2024-09 to 4,929.07 kWh in 2025-04. Full energy belongs to the session-start period, not measured hourly grid load.
- Capacity and active-charger-energy concerns each flag 0 sessions; the union is 0. Sensitivity retains all 200,000 sessions (100%) and 3,014,172.81 kWh (100% of baseline). No comparison chart is exported because nothing is excluded; flag counts are reported as validation. This does not verify real measurements: this is synthetic consistency, not corrected/ground-truth data.

All six tables reconcile counts and energy. See [methodology](demand_methodology.md) and [migration notes](dataset_migration.md) for port/time/active-energy semantics and remaining Power BI updates.

## Notebooks, figures and next steps

- [01_preprocessing.ipynb](../notebooks/01_preprocessing.ipynb): preparation decisions and compact quality summaries.
- [02_demand_analysis.ipynb](../notebooks/02_demand_analysis.ipynb): verified tables, interpretations and linked chart files; keep the figures directory when sharing.
- [03_demand_analysis_code_and_charts.ipynb](../notebooks/03_demand_analysis_code_and_charts.ipynb): meaningful plotting code and **ten embedded inline charts**; no saved images required to execute.
- [outputs/demand/figures/](../outputs/demand/figures/): ten figures, each in PNG (300 dpi); daily smoothing requires seven dates, so the first six means are missing.
- [Concise findings](member2_findings.md) and [project plan](project_plan.md): validated interpretation, agreed responsibilities and remaining scope. Station/queue analysis, Power BI integration and final individual write-ups remain unfinished.

Baek, Lee & Kim (2024), [Scientific Data 11, 262](https://doi.org/10.1038/s41597-024-02942-9), motivates temporal inspection; it is neither the source of this CSV nor proof of these results. The generator internals/licence and real-world applicability remain evidence limitations; timezone is explicitly Asia/Kolkata.


## Additional Power BI imports

Import the five additional CSVs listed in the methodology as separate summary grains. Relate location-hour rows to Location_Type/hour dimensions; the repeated location_session_count denominator must not be summed across hours. Under date/area filters, recompute percentages from session-level data rather than reusing all-period fixed percentages. `daily_weekday_counts` supplies the calendar-date distribution; do not average weekday quartiles under incompatible filters. Time-period and charger mean/median energy use valid-energy sessions, while duration counts are independent. For interactive medians/quartiles, calculate from eligible session/date observations instead of averaging aggregate medians. Retain active and connected duration measures as separate quantities. All flags are false in this sample, so show a validation result rather than a sensitivity chart. Ten PNGs are exported for the current data; no vector files are required.

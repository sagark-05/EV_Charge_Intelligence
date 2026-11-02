# Team handoff

## Dataset transfer and reproduction

Source status: **shared by team member; original source and licence unverified**. Collection methodology and timezone are unverified. Obtain the same CSV directly from the team member through the team's agreed transfer channel and place it at `data/raw/EV_Dataset.csv`; GitHub does not contain dataset CSVs. Do not substitute the research paper's dataset. Keep the raw file unchanged.

From the repository root, using Python 3.9 or newer on Linux/macOS:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
sha256sum data/raw/EV_Dataset.csv
.venv/bin/python -m pytest -q
.venv/bin/python src/data_preparation.py
.venv/bin/python src/demand_analysis.py
.venv/bin/python src/demand_visualization.py
.venv/bin/python scripts/execute_notebook.py notebooks/01_preprocessing.ipynb
.venv/bin/python scripts/execute_notebook.py notebooks/02_demand_analysis.ipynb
.venv/bin/python scripts/execute_notebook.py notebooks/03_demand_analysis_code_and_charts.ipynb
sha256sum data/raw/EV_Dataset.csv data/processed/charging_sessions.csv
```

Expected SHA-256 fingerprints for this handoff:

- Raw: `17bf329c2db9b3ee686a441d705750b8df006b0a2e88bb05d590e021b58739cf`.
- Cleaned: `fa9d6b8401f891f15f47a94289362312a9072ecfe3f2e5207c76fd8c9cdcc50a`.

The cleaned hash identifies the current preparation output; different library versions may affect serialization. Compare counts/definitions and investigate any difference rather than silently substituting data. Dependencies use compatible version ranges, not a frozen environment. Jupyter execution needs local kernel sockets. On Windows, use the equivalent virtual-environment Python path; `sha256sum` commands above assume a shell providing that utility.

All CSVs, including aggregate demand exports, are ignored and regenerated locally. Code, tests, docs, executed notebooks, aggregate JSON reports and PNG/SVG figures are versioned. Quality reports contain aggregates and hashes, not full session records. Rejected and flagged CSVs remain local audit files; do not add them with `git add -f`.

## Inputs for the remaining modules

**Member 3:** use `data/processed/charging_sessions.csv`, [data dictionary](data_dictionary.md) and `outputs/data_quality/quality_report.json`. `Source_Row_Number` supports audit lookup; local `rejected_sessions.csv` and `flagged_records.csv` carry explicit reasons. Energy/queue `*_Validity` columns distinguish valid, missing, nonnumeric, nonfinite and negative values. Numeric validity requires finite values >= 0; zero is allowed. Use valid measurements for their own metrics without deleting valid demand sessions. All 1,000 station IDs have inconsistent names/cities/states: station-ID comparisons depend on identifier reliability. Do not invent mappings or make geographic recommendations.

**Member 4:** use the cleaned session-level CSV and a date table spanning the inclusive represented dates. Preserve IDs and explicitly parse timestamps as `DD-MM-YYYY HH:MM`; do not infer timezone. Derived date/hour/weekday/weekend/year-month fields are provided. Use `outputs/demand/*.csv` and `analysis_summary.json` as fixed reference checks under matching filters. Build interactive measures from session-level data; fixed aggregate averages must not be reused under incompatible filters. Label baseline/sensitivity scenarios and valid-energy coverage separately. Power BI implementation remains future work.

## Validated reference totals and metric rules

- Preparation: **200,000 input = 0 exact duplicates removed + 0 rejected + 200,000 accepted**. All accepted rows are flagged for station-mapping inconsistencies, not rejected.
- Coverage: `01-01-2024 00:00` through `30-12-2025 23:53`, **730 inclusive dates**. Complete collection, including zero-session dates, is an assumption; timestamps do not prove uptime or complete first/last-day observation. December 2025 is a partial boundary month (30/31 dates).
- Demand: count unique valid session starts; average = sessions / represented calendar days. Weekday and weekday–hour denominators count that weekday's dates; weekday/weekend count their respective dates; monthly values keep years separate. Overall **273.9726 starts/day**; weekday **274.5785**, weekend **272.4519**. Hourly demand is nearly uniform (relative index **0.97668–1.01760**).
- Energy: **200,000 numerically valid sessions**, **9,493,219.61 kWh**, **47.4661 kWh/valid-energy session**. Total sums valid measurements; energy/session divides by valid-energy sessions; energy/day divides by represented dates. No valid energy means missing totals/averages, not measured zero. Invalid energy never removes demand rows.
- Plausibility: **49,101** capacity flags, **71,740** nominal-charger-energy flags, **23,488** overlap, **97,353** union. Sensitivity retains **102,647 sessions (51.32%)** and **3,648,439.11 kWh (38.43% of baseline energy)**, without changing baseline demand. It is not corrected/ground-truth data; sample composition differs.

All six baseline tables independently reconcile session counts, energy-validity counts and recorded-energy totals. Full session energy belongs to its start period in these summaries, not a measured hourly electricity-load profile. Recorded duration is not confirmed active charging. Session counts/`Peak_Hour` labels do not establish congestion; true utilization requires reliable capacity and availability data. No causes or statistical significance are inferred. See [demand methodology](demand_methodology.md) for exact formulas and missing-value semantics.

## Notebooks, figures and next steps

- [01_preprocessing.ipynb](../notebooks/01_preprocessing.ipynb): preparation decisions and compact quality summaries.
- [02_demand_analysis.ipynb](../notebooks/02_demand_analysis.ipynb): verified tables, interpretations and linked chart files; keep the figures directory when sharing.
- [03_demand_analysis_code_and_charts.ipynb](../notebooks/03_demand_analysis_code_and_charts.ipynb): meaningful plotting code and **seven embedded inline charts**; no saved images required to execute.
- [outputs/demand/figures/](../outputs/demand/figures/): seven figures, each in PNG (300 dpi) and SVG; daily smoothing requires seven dates, so the first six means are missing.
- [Concise findings](member2_findings.md) and [project plan](project_plan.md): validated interpretation, agreed responsibilities and remaining scope. Station/queue analysis, Power BI integration and final individual write-ups remain unfinished.

Baek, Lee & Kim (2024), [Scientific Data 11, 262](https://doi.org/10.1038/s41597-024-02942-9), motivates temporal inspection; it is neither the source of this CSV nor proof of these results. Original source/licence, methodology, timezone and reliable station mappings remain external evidence limitations.

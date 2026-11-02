# EVCharge Intelligence

**A Data-Driven Analysis of EV Charging Demand, Utilization and Peak-Time Congestion**

The agreed project covers descriptive Python analysis and Power BI visualization of session-start demand, recorded energy, station activity and potential congestion indicators. ML is not required. See the [project plan](docs/project_plan.md) for responsibilities, metric definitions, limitations, phases and remaining work.

The Data Preparation module is implemented by Sagar K (PES2UG24CS424), who also owns the Temporal Demand and Energy Analysis module. He is covering preparation because the Data Preparation module owner's laptop is unavailable; module ownership and implementation contributions remain separate. Temporal Demand and Energy Analysis calculations, visualizations, analysis notebook and concise findings are implemented. Station analysis and Power BI integration remain planned work.

Source status: **shared by team member; original source and licence unverified**. Collection methodology and timezone are also **unverified**; no claim is made that the dataset is real-world or synthetic.

## Data Preparation

From the repository root (Python 3.9 or newer):

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python src/data_preparation.py
.venv/bin/python scripts/execute_notebook.py
sha256sum data/raw/EV_Dataset.csv
```

Optional paths: `--input PATH --processed-dir PATH --quality-dir PATH`.
The source CSV is read only. SHA-256 values before and after reading are recorded in the report. All dataset CSVs, environments and caches are ignored by Git; supply the raw CSV locally.

Outputs:

- `data/processed/charging_sessions.csv`: accepted records, original columns plus source row number, derived time features, measurement validity and energy plausibility flags.
- `data/processed/rejected_sessions.csv`: quarantined records with source row number and explicit reasons.
- `outputs/data_quality/flagged_records.csv`: all records with any quality issue, including rejected records.
- `outputs/data_quality/quality_report.json`: aggregate counts, policies and hashes; contains no full records.

Exact duplicate rows are compared across all original text fields; the first occurrence is retained. Every remaining record sharing a nonblank session ID is rejected as a conflict. Missing IDs, invalid timestamps and end-before-start records are also rejected. Counts and source row numbers refer to CSV records (header is row 1), not physical lines inside quoted multiline fields. Removed duplicate copies are counted, not repeated in the rejected export.

Blank/whitespace-only fields are missing. Other source text is preserved, including identifier whitespace and literal strings such as `NA`; no identifier normalization, station mapping, timezone conversion or measurement imputation is performed. Station conflicts use all deduplicated rows, including rejected ones, and ignore blank mapping values. Calendar, duration, missing-field and station issues are flagged without changing source values. Duration tolerance is 0.01 minute; timestamps have minute precision. Weekday names must match English full names; month must be numeric 1–12. Timestamp values must strictly match `DD-MM-YYYY HH:MM` and a valid calendar date.

See [data dictionary](docs/data_dictionary.md) for field definitions. Review flags before choosing fields for later analysis; acceptance establishes usable identity and timestamps, not correctness of every measurement.

## Status and interpretation

The existing [quality report](outputs/data_quality/quality_report.json) reports 200,000 input and accepted rows, zero duplicate removals/rejections, and balanced reconciliation. All 1,000 station IDs have multiple names, cities and states, flagging all 200,000 records. Station comparisons therefore depend on identifier reliability; do not guess mappings or make geographic recommendations from them. Reported hashes match. The pipeline and preprocessing notebook have been executed with the extended Phase 1 implementation.

Phase 1 now includes derived time features and an executed [preprocessing notebook](notebooks/01_preprocessing.ipynb), which calls the existing preparation module. The runner uses the active Python interpreter and saves compact outputs without timing metadata. Notebook paths support repository-root or notebooks-directory execution. To rerun from `notebooks/`, use `../.venv/bin/python ../scripts/execute_notebook.py`.

Accepted starts span `01-01-2024 00:00` through `30-12-2025 23:53`: 730 inclusive dates, all with observed starts. Future calendar averages assume complete collection over that range, including zero-session dates; timestamps do not verify collection uptime or complete first/last-day coverage.

Both energy and queue time have 200,000 numerically valid values and zero missing/nonnumeric/nonfinite/negative values. Separate plausibility concerns flag 49,101 sessions above battery capacity and 71,740 above nominal charger energy (elapsed timestamp duration). Concerns can overlap and do not exclude demand or numerically valid energy. No measurements are corrected. See the dictionary for nullable flags and validity meanings.

Derived features are always recomputed from explicitly parsed timestamps, including when feature columns already exist. Original timestamp formats remain unchanged. Source origin/licence, collection methodology, timezone and reliable station mappings remain unresolved evidence limitations. Session-start demand does not establish congestion or true utilization, and supplied `Peak_Hour` labels do not prove observed peaks. Station analysis and Power BI remain later work.

## Temporal Demand and Energy Analysis

After preparation, run from the repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python src/demand_analysis.py
sha256sum data/raw/EV_Dataset.csv data/processed/charging_sessions.csv
```

Optional arguments: `--input PATH --output-dir PATH --raw-input PATH`. Defaults use the cleaned CSV and `outputs/demand/`; the repository raw CSV is fingerprinted if available. No new dependencies are required. Both inputs remain unchanged.

Outputs: `hourly_demand.csv`, `daily_demand.csv`, `weekday_demand.csv`, `weekday_weekend_demand.csv`, `day_hour_demand.csv`, `monthly_demand.csv`, `monthly_energy_sensitivity.csv`, and aggregate `analysis_summary.json`. See [demand methodology](docs/demand_methodology.md) for formulas, missing-energy semantics, calendar denominators and the sensitivity scenario.

The execution on 200,000 sessions reports 9,493,219.61 kWh recorded energy (all measurements numerically valid), 273.97 sessions/day and 47.47 kWh/valid-energy session. Hourly relative demand ranges from 0.97668 to 1.01760: a nearly uniform profile, with hour 08 highest and hour 09 lowest. December 2025 is a partial boundary month. Energy is assigned to session-start time and does not represent measured hourly grid load.

The sensitivity scenario excludes the union of 97,353 plausibility-flagged sessions (23,488 overlap), retaining 102,647 sessions and 3,648,439.11 kWh. Baseline demand counts never change. This is not corrected data; exclusions can change sample composition. All six baseline tables reconcile counts and energy independently, with fixed category grids and an inclusive calendar.

## Temporal Demand and Energy Analysis: visualizations and notebook

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python src/demand_visualization.py
.venv/bin/python scripts/execute_notebook.py notebooks/02_demand_analysis.ipynb
```

The plotting CLI reads existing verified summaries (`--input-dir`, default `outputs/demand/`) and saves seven figures to `figures/` (`--output-dir` can override): hourly demand, daily demand with trailing 7-day mean, weekday/weekend panels, weekday–hour heatmap, monthly demand, hourly/monthly recorded-energy panels, and monthly energy sensitivity with retained-sample context. Each is available as 300-dpi PNG and SVG; no aggregation logic is duplicated.

Open [02_demand_analysis.ipynb](notebooks/02_demand_analysis.ipynb) for compact tables, linked figures and interpretations; keep `outputs/demand/figures/` beside the repository because images are linked rather than embedded. The notebook imports existing analysis/plotting functions, revalidates cleaned data against saved summaries and checks protected file hashes. It resolves paths from repository root or `notebooks/`. The notebook runner still defaults to preprocessing when no notebook argument is supplied.

See [Temporal Demand and Energy Analysis findings](docs/member2_findings.md) for the concise results. Weekdays average 274.58 starts/day versus 272.45 on weekends. Monthly demand is 270.00–281.13/day; the highest month is partial December 2025. Hourly demand remains nearly uniform. The sensitivity retains 51.32% of valid-energy sessions and 38.43% of recorded energy; sample composition differs and this is not corrected data. Zero-based axes and a sequential heatmap avoid exaggerating these descriptive differences.

All seven rendered figures were visually inspected for clipping, overlap and readability. Raw/cleaned files and Phase 2 summaries are preserved. Station/queue analysis, Power BI integration and the final individual write-up are outside this step.

For executable plotting code with seven embedded inline charts, open [03_demand_analysis_code_and_charts.ipynb](notebooks/03_demand_analysis_code_and_charts.ipynb). It imports existing analysis/layout helpers, needs no saved chart images, and preserves the original notebook and figure exports. Run it with `.venv/bin/python scripts/execute_notebook.py notebooks/03_demand_analysis_code_and_charts.ipynb`.

See [team handoff](docs/team_handoff.md) for dataset transfer, exact reproduction commands, reference totals, and inputs for the remaining station and Power BI work.

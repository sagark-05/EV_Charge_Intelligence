# EVCharge Intelligence

**A Data-Driven Analysis of EV Charging Demand, Utilization and Peak-Time Congestion**

EVCharge Intelligence uses Python analysis and Power BI visualization to explore EV charging-session demand, recorded energy, station activity and potential congestion indicators.

The current implementation includes data preparation, quality validation, temporal demand and energy analysis, seven visualizations, and executable Jupyter notebooks. Station analysis and Power BI integration remain planned.

See the [project plan](docs/project_plan.md) for scope, metric definitions and implementation phases.

## Dataset

Place the original dataset at:

```text
data/raw/EV_Dataset.csv
```

The supplied dataset contains **200,000 charging sessions and 38 original columns**.

**Source status:** shared by a team member; original source, collection methodology, reuse licence and timezone are unverified.

Dataset CSVs are excluded from Git. Obtain the input file separately before running the project.

## Setup

Run from the repository root using Python 3.9 or newer:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The commands below use the Ubuntu/Linux virtual-environment path.

## Run the Pipeline

Run these commands in order:

```bash
.venv/bin/python src/data_preparation.py
.venv/bin/python src/demand_analysis.py
.venv/bin/python src/demand_visualization.py
```

Execute the notebooks:

```bash
.venv/bin/python scripts/execute_notebook.py notebooks/01_preprocessing.ipynb
.venv/bin/python scripts/execute_notebook.py notebooks/02_demand_analysis.ipynb
.venv/bin/python scripts/execute_notebook.py notebooks/03_demand_analysis_code_and_charts.ipynb
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```

Verify input fingerprints:

```bash
sha256sum data/raw/EV_Dataset.csv data/processed/charging_sessions.csv
```

## Data Preparation

The preparation pipeline validates session identity, timestamps, duration, calendar fields, station mappings, and energy/queue measurements.

It preserves the original CSV and exports:

| Output | Contents |
|---|---|
| `data/processed/charging_sessions.csv` | Accepted records, original columns, derived features and quality flags |
| `data/processed/rejected_sessions.csv` | Quarantined records with source row numbers and reasons |
| `outputs/data_quality/flagged_records.csv` | Records with quality issues, including rejected records |
| `outputs/data_quality/quality_report.json` | Aggregate counts, policies, coverage and hashes |

### Validation Rules

- Exact duplicate rows are compared across original text fields; the first occurrence is retained.
- After exact deduplication, remaining records sharing a nonblank session ID are rejected as conflicts.
- Missing IDs, invalid timestamps and end-before-start records are rejected.
- Timestamps must match `DD-MM-YYYY HH:MM` and represent valid dates.
- Duration comparisons use a tolerance of 0.01 minute.
- Missing fields, duration/calendar mismatches and station inconsistencies are flagged without guessed corrections.
- Blank or whitespace-only fields are treated as missing. Other source text is preserved.
- No identifier normalization, timezone conversion or measurement imputation is performed.

Source row numbers identify CSV records, with the header counted as row 1. Removed duplicate copies are counted separately rather than repeated in the rejected export.

### Derived Features

- `Charging_Date`
- `Charging_Hour`
- `Weekday_Index`
- `Weekday_Name`
- `Is_Weekend`
- `Year_Month`
- `Calculated_Session_Duration_Min`

Features are deterministically recomputed from parsed timestamps. Original timestamp formats remain unchanged.

Energy and queue measurements are numerically valid when finite and nonnegative. Energy above battery capacity or nominal charger energy is flagged separately as a plausibility concern; these flags do not automatically remove sessions.

Optional preparation arguments:

```text
--input PATH --processed-dir PATH --quality-dir PATH
```

See the [data dictionary](docs/data_dictionary.md) for definitions and detailed policies.

## Temporal Demand and Energy Analysis

The analysis measures session starts and recorded energy by:

- Hour of day
- Calendar date
- Day of week
- Weekday versus weekend
- Weekday–hour combination
- Year and month

It exports these files under `outputs/demand/`:

```text
hourly_demand.csv
daily_demand.csv
weekday_demand.csv
weekday_weekend_demand.csv
day_hour_demand.csv
monthly_demand.csv
monthly_energy_sensitivity.csv
analysis_summary.json
```

Metrics include session counts, represented calendar days, average sessions/day, valid-energy counts, total recorded energy, average energy/session and average energy/day.

### Interpretation Rules

- Calendar averages assume complete collection between the earliest and latest observed dates.
- Zero-session dates are included, but timestamps do not establish collection uptime.
- Weekday/weekend comparisons use their respective calendar-day counts.
- Year-months are kept separate, and partial boundary months are identified.
- Full session energy is attributed to session-start time. It is not measured hourly grid load.
- Invalid energy does not remove an otherwise valid session from demand analysis.
- The hourly relative demand index compares each hour’s average with the mean across all 24 hours.
- Session-start demand alone does not establish congestion or true utilization.

Optional analysis arguments:

```text
--input PATH --output-dir PATH --raw-input PATH
```

See [demand methodology](docs/demand_methodology.md) for formulas, missing-energy handling and reconciliation checks.

## Visualizations and Notebooks

Seven figures are exported as **300-dpi PNG and SVG** files under:

```text
outputs/demand/figures/
```

They cover:

1. Hourly demand
2. Daily demand with a trailing seven-day mean
3. Weekday and weekday/weekend comparisons
4. Weekday–hour heatmap
5. Monthly demand
6. Hourly and monthly recorded-energy profiles
7. Monthly energy sensitivity comparison

The plotting CLI reads the existing summary tables. Optional arguments:

```text
--input-dir PATH --output-dir PATH
```

| Notebook | Purpose |
|---|---|
| [01_preprocessing.ipynb](notebooks/01_preprocessing.ipynb) | Preparation workflow and quality summaries |
| [02_demand_analysis.ipynb](notebooks/02_demand_analysis.ipynb) | Compact tables, linked charts and interpretations |
| [03_demand_analysis_code_and_charts.ipynb](notebooks/03_demand_analysis_code_and_charts.ipynb) | Executable plotting code with seven embedded chart outputs |

Keep the repository’s `outputs/demand/figures/` directory when sharing the linked-chart notebook. The embedded-chart notebook can display its saved outputs without those image files; rerunning requires the documented data and dependencies.

Notebook paths support execution from the repository root or `notebooks/`. The notebook runner defaults to preprocessing when no notebook argument is supplied.

## Recorded Results

The completed execution reports:

| Metric | Result |
|---|---:|
| Accepted sessions | 200,000 |
| Rejected sessions | 0 |
| Exact duplicates removed | 0 |
| Represented calendar days | 730 |
| Average session starts/day | 273.97 |
| Total recorded energy | 9,493,219.61 kWh |
| Average recorded energy/valid-energy session | 47.47 kWh |
| Weekday starts/day | 274.58 |
| Weekend starts/day | 272.45 |

Observed starts span **1 January 2024, 00:00 to 30 December 2025, 23:53**.

Hourly demand is nearly uniform: the relative index ranges from **0.97668 to 1.01760**. The highest aggregate count is at **08:00**, with 8,480 starts; the lowest is at **09:00**, with 8,139 starts.

Monthly demand ranges from **270.00 to 281.13 starts/day**. The highest month is partial December 2025, which should not be treated as evidence of a seasonal peak.

See [Demand and Energy Findings](docs/member2_findings.md) for interpretations.

## Data Quality and Limitations

- All 1,000 station IDs have multiple station names, cities and states. Station comparisons depend on identifier reliability; geographic recommendations are unsupported by these mappings.
- Energy and queue values are numerically valid, but numerical validity does not establish measurement accuracy.
- Energy plausibility concerns affect 49,101 sessions above battery capacity and 71,740 above nominal charger energy.
- These checks overlap in 23,488 sessions, affecting **97,353 unique sessions**.
- The sensitivity scenario excludes their union, retaining **102,647 sessions** and **3,648,439.11 kWh**.
- This retains **51.32% of sessions** and **38.43% of recorded energy**. It is an alternative sample, not corrected or verified data.
- Baseline session-demand counts remain unchanged.
- Source provenance, licence, timezone and collection completeness remain unverified.
- Supplied `Peak_Hour` labels are not used as proof of observed demand peaks.
- Connected occupancy, active charging, delivered energy, session starts and queue time are different measurements.

## Research Basis

Baek, K., Lee, E., & Kim, J. (2024). *A dataset for multi-faceted analysis of electric vehicle charging transactions*. Scientific Data, 11, 262.

https://doi.org/10.1038/s41597-024-02942-9

The project adapts the paper’s temporal charging-pattern analysis ideas. The paper’s dataset is separate from the supplied CSV. Our session-start metrics differ from its connection/coupling measurements; calendar normalization and the relative demand index are project design choices.

## Verification

The latest reported local verification includes:

- **49 passing tests**
- Executed and validated notebooks
- Independent session-count and energy reconciliation across all six baseline summary tables
- Verified sensitivity partitions and temporal category ordering
- Visual inspection of all seven figures
- Unchanged raw and cleaned input hashes
- Passing `git diff --check`

These are local verification results, not a claim that GitHub Actions checks are configured.

## Team Handoff

See [team handoff](docs/team_handoff.md) for dataset transfer, reproduction commands, reference totals and integration guidance.

Remaining project work includes station activity/congestion-indicator analysis and Power BI integration. Interactive dashboard measures should use appropriate session-level data and calendar denominators rather than applying fixed aggregate averages under incompatible filters.

# EVCharge Intelligence

**A Data-Driven Analysis of EV Charging Demand, Utilization and Peak-Time Congestion**

EVCharge Intelligence uses Python analysis and Power BI visualization to explore EV charging-session demand, recorded energy, station activity and potential congestion indicators.

The current implementation includes data preparation, quality validation, temporal demand and energy analysis, ten visualizations for the current dataset, and executable Jupyter notebooks. Station analysis and Power BI integration remain planned.

See the [project plan](docs/project_plan.md) for scope, metric definitions and implementation phases.

## Dataset

Place the original dataset at:

```text
data/raw/EV_Dataset_India.csv
```

The supplied dataset contains **200,000 generated synthetic Indian charging sessions and 32 original columns**.

**Source status:** generated synthetic Indian charging data supplied by the team. The CSV declares `Asia/Kolkata`; generator code, seed, sampling/loss assumptions and reuse licence were not supplied. The old `data/raw/EV_Dataset.csv` is preserved. See [dataset migration](docs/dataset_migration.md) for schema changes and Power BI impacts.

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
sha256sum data/raw/EV_Dataset_India.csv data/processed/charging_sessions.csv
```

## Data Preparation

The preparation pipeline validates session identity, timestamps, duration, calendar fields, station/port mappings, arrivals, active charging, overlaps, and energy/queue measurements.

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
- All four timestamps (arrival, start, charging end, release) are localized to `Asia/Kolkata`; exports retain day-first wall-time strings plus `Timezone`. No measurement imputation is performed.
- Station mappings include area/location type, coordinates, ports and charger specifications. All participants in overlapping `[Session_Start, Session_End)` intervals on the same station/port are flagged.
- Arrival <= start <= charging end <= session end and integer port assignment are validated. Recorded queue/active durations are checked against timestamps; energy limits use active charging hours, not port occupancy.

Source row numbers identify CSV records, with the header counted as row 1. Removed duplicate copies are counted separately rather than repeated in the rejected export.

### Derived Features

- `Charging_Date`
- `Charging_Hour`
- `Weekday_Index`
- `Weekday_Name`
- `Is_Weekend`
- `Year_Month`
- `Calculated_Session_Duration_Min` (port occupancy)
- `Arrival_Date`, `Arrival_Hour`
- `Calculated_Queue_Time_Min`, `Calculated_Active_Charging_Duration_Min`
- `Post_Charging_Occupancy_Min`, `Station_Port_Key`

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

Ten figures are exported for the current dataset as **300-dpi PNG** files under:

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
7. Location-type hourly percentage profiles
8. Weekday variability box plots
9. Time-period energy per session
10. Charger-type energy/active/connected comparison

The monthly sensitivity comparison remains available only when true/false plausibility flags provide a retained/excluded contrast. For this dataset all flags are false; validation counts are reported instead of a chart.

The plotting CLI reads the existing summary tables. Optional arguments:

```text
--input-dir PATH --output-dir PATH
```

| Notebook | Purpose |
|---|---|
| [01_preprocessing.ipynb](notebooks/01_preprocessing.ipynb) | Preparation workflow and quality summaries |
| [02_demand_analysis.ipynb](notebooks/02_demand_analysis.ipynb) | Compact tables, linked charts and interpretations |
| [03_demand_analysis_code_and_charts.ipynb](notebooks/03_demand_analysis_code_and_charts.ipynb) | Executable plotting code with ten embedded chart outputs |

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
| Total recorded energy | 3,014,172.81 kWh |
| Average recorded energy/valid-energy session | 15.07 kWh |
| Weekday starts/day | 277.05 |
| Weekend starts/day | 266.25 |

Observed starts span **1 January 2024, 01:53 to 30 December 2025, 23:53 (Asia/Kolkata)**.

Hourly demand is no longer nearly uniform: relative index 0.10560–2.06376. Hour 09 has the most starts (17,198; 23.56/calendar day), versus hour 01 (880; 1.21/day). This is the generated sample's pattern, not evidence of real congestion or actual Indian charging behavior.

Monthly starts/day range from 220.93 in 2024-09 to 326.17 in 2025-04. Partial boundary months: 2025-12. Partial coverage is not a missing-data marker; the synthetic differences do not establish real seasonality or a causal trend.

See [Demand and Energy Findings](docs/member2_findings.md) for interpretations.

## Data Quality and Limitations

- The 997 station IDs present have consistent name/city/state/area/location/port/charger mappings; no port overlaps or structural timestamp errors were found.
- Energy and queue values are numerically valid. All energy values pass capacity, battery-level-delta and calculated active-power checks in this run.
- The sensitivity scenario excludes no sessions: 200,000 sessions and 3,014,172.81 kWh are retained (100%). Baseline demand remains unchanged.
- This is generated synthetic data; the patterns do not establish actual Indian behavior, measurement accuracy or real equipment availability.
- Generator code, seed, sampling/loss assumptions and reuse licence were not supplied. Local timezone is explicitly Asia/Kolkata.
- Supplied `Peak_Hour` labels are not used as proof of observed demand peaks.
- Arrivals, session starts, port occupancy, active charging, delivered energy and queue time are distinct. See the migration notes for removed fields and Power BI refresh requirements.

## Research Basis

Baek, K., Lee, E., & Kim, J. (2024). *A dataset for multi-faceted analysis of electric vehicle charging transactions*. Scientific Data, 11, 262.

https://doi.org/10.1038/s41597-024-02942-9

The project adapts the paper’s temporal charging-pattern analysis ideas. The paper’s dataset is separate from the generated Indian CSV. Our session-start metrics differ from its connection/coupling measurements; calendar normalization and the relative demand index are project design choices.

## Verification

The latest reported local verification includes:

- **68 passing tests**
- Executed and validated notebooks
- Independent session-count and energy reconciliation across all six baseline summary tables
- Verified sensitivity partitions and temporal category ordering
- Visual inspection of the regenerated figures
- Both raw CSVs preserved; regenerated cleaned-data hash checked during analysis and notebook execution
- Passing `git diff --check`

These are local verification results, not a claim that GitHub Actions checks are configured.

## Team Handoff

See [team handoff](docs/team_handoff.md) for dataset transfer, reproduction commands, reference totals and integration guidance.

Remaining project work includes station activity/congestion-indicator analysis and Power BI integration. Interactive dashboard measures should use appropriate session-level data and calendar denominators rather than applying fixed aggregate averages under incompatible filters.


## Additional temporal comparisons

Five new Power BI-ready CSVs are regenerated under `outputs/demand/`: `location_type_hourly.csv`, `daily_weekday_counts.csv`, `weekday_variability.csv`, `time_period_energy.csv`, and `charger_type_comparison.csv`. The location profile percentages sum to 100% within each represented type; weekday quartiles use the complete daily calendar. Per-session period energy uses five non-overlapping bins; charger summaries keep energy, active charging and connected occupancy separate and report supplied-duration mismatches.

Both analysis notebooks now include code, inline charts and calculated interpretations for these four analyses. The code-and-charts notebook embeds ten charts for the current dataset. The exporter produces exactly one PNG per intended chart and removes only its known generated vector copies or inactive sensitivity PNG, preserving unrelated user files. No SVG files are required. See the methodology for synthetic assumptions and the handoff for Power BI grain/filter rules.

# EVCharge Intelligence

**A Data-Driven Analysis of EV Charging Demand, Utilization and Peak-Time Congestion**

## Objective and responsibilities

Analyze charging-session demand, recorded energy, station activity, and potential congestion indicators using Python and Power BI. The scope is descriptive analysis and visualization; ML is not required. Utilization and congestion claims remain conditional on the evidence available.

| Module owner | Agreed work |
| --- | --- |
| Member 1 - Manoj KUmar, PES2UG25C610| Dataset/source documentation, validation, preprocessing, derived time features, data dictionary, preprocessing notebook, cleaned dataset. |
| Member 2 — Sagar K, PES2UG24CS424 | Hourly, date-wise daily, weekday/weekend, day–hour, and year-month session-start demand; temporal energy trends; peak/low periods; analysis notebook, charts, summary tables, findings. |
| Member 3 — Vageesh Hiremath, PES2UG24CS424| Station-wise session counts and energy, duration analysis, reported queue times, unusual patterns, potential congestion indicators. |
| Member 4 — Nikhil K R, PES2UG25CS815| Power BI data model, measures, interactive filters, dashboard, screenshots, integrated storytelling. |


## Research basis and interpretation

Baek, K., Lee, E., & Kim, J. (2024). *A dataset for multi-faceted analysis of electric vehicle charging transactions*. Scientific Data, 11, 262. [https://doi.org/10.1038/s41597-024-02942-9](https://doi.org/10.1038/s41597-024-02942-9).

Adapt temporal-pattern analysis ideas, not the paper's numerical results. Its dataset is separate from ours. Session-start counts differ from connection/coupling profiles: they do not measure simultaneous connected vehicles or active charging. Calendar normalization and any project demand index are our design choices; document the index formula, reference baseline and interpretation before use.

## Metric agreement

| Metric | Definition |
| --- | --- |
| Session count | Valid unique session starts in the selected period. |
| Average sessions/day | Sessions / represented calendar days. |
| Total energy | Sum of valid recorded `Energy_Delivered_kWh`. |
| Average energy/session | Valid energy total / number of valid-energy sessions. |
| Average energy/day | Valid energy total / represented calendar days. |
| Duration | Recorded `Session_Duration_Min`; do not assume active charging time. |
| Queue summaries | Median and 90th percentile of valid recorded `Queue_Time_Min`. |

Preparation now classifies energy/queue measurements as valid (finite numeric >= 0), missing, nonnumeric, nonfinite or negative; zero is allowed. Planned summaries must use these rules, report excluded measurements and document the quantile method. Invalid energy must not remove otherwise valid demand rows. Return unavailable values for zero denominators.

Before normalizing, state the calendar coverage and whether zero-session dates mean observed inactivity or unknown coverage. Future calendar averages assume complete collection across the inclusive observed range, including zero-session dates; disclose this assumption and retain those dates. Derive separate year-month values; label partial boundary months and show their represented-day denominators. Do not combine the same month across different years silently.

Assigning full session energy to its start hour means **energy associated with sessions starting then**, not measured hourly grid load. Session counts alone do not establish congestion. True utilization requires reliable capacity and availability data; the supplied uptime percentage alone does not establish these.

## Dataset limitations

Active input is **generated synthetic Indian charging data**, `data/raw/EV_Dataset_India.csv`; Asia/Kolkata is declared explicitly. The legacy CSV is preserved. Generator code, seed, distributions/loss assumptions and reuse licence were not supplied. Station mappings and port occupancy are validated internally, not verified against real infrastructure. The input is generated synthetic Indian charging data. Station mappings are internally consistent in this run, not independently verified locations. Generator code, seed, distribution/efficiency assumptions and reuse licence were not supplied. Keep arrivals, active charging and port occupancy separate. Counts alone do not prove congestion; port counts do not establish operational availability.

## Architecture and planned deliverables

**Raw CSV → preparation module → cleaned session-level data → demand/energy and station modules → charts/notebooks → Power BI.**

Reusable calculations belong in Python modules. Notebooks import those functions and explain decisions and results. Preserve `Session_ID`, `Session_Start` and other original column names; add clearly documented time features. Keep the original CSV unchanged and retain quality reports and row-level audit outputs.

Required temporal visuals: hourly demand, date-wise daily trend, weekday comparison, day–hour heatmap, year-month demand trend, and relevant hourly/monthly energy visuals. Related metrics may share a figure when readable. Include weekday/weekend comparisons, peak/low summaries, station summaries and evidence-based findings.

Power BI uses session-level data with a date table for interactive measures. Python summaries support verification and fixed summaries; do not reuse fixed aggregate averages under incompatible filters. Verify measures and denominators against Python under matching filters.

## Phases and current evidence

| Phase | Planned completion criterion | Current status |
| --- | --- | --- |
| 0 | Plan and metric agreement | This document records scope and definitions; coverage assumption and hourly relative-index formula are documented in the demand methodology. |
| 1 | Complete/review preparation, time features, preprocessing notebook | Preparation module, time features, validity/plausibility flags, dictionary, tests, exported artifacts and executed preprocessing notebook are available; evidence limitations remain. |
| 2 | Demand/energy calculations and station analysis | Member 2 temporal demand/recorded-energy module, six summaries and monthly energy sensitivity scenario implemented and executed; Member 3 station work remains planned. |
| 3 | Verified charts, notebooks and findings | Member 2 ten figures for the current dataset (PNG), executed analysis notebook and concise findings completed; figures visually inspected. |
| 4 | Power BI integration and end-to-end verification | Planned; no Power BI artifact present. |
| 5 | Individual one-page write-up, README, GitHub cleanup and demo | Planned; README covers scope, preparation, temporal analysis, plotting and notebook commands. |

The current [quality report](../outputs/data_quality/quality_report.json) records 200,000 accepted sessions, no duplicate removals/rejections/flags, consistent mappings for the 997 station IDs present and no station/port overlaps. Arrival, active charging and occupancy are distinct; energy limits use calculated active charging hours.

Accepted session starts span 01-01-2024 01:53 to 30-12-2025 23:53 in Asia/Kolkata, across 730 inclusive dates. Complete collection including zero-session dates is an assumption; timestamps do not establish uptime or complete boundary-day observation.

Hourly demand is no longer nearly uniform: relative index 0.10560–2.06376. Hour 09 has the most starts (17,198; 23.56/calendar day), versus hour 01 (880; 1.21/day). This is the generated sample's pattern, not evidence of real congestion or actual Indian charging behavior.

All 200,000 energy measurements are numerically valid: 3,014,172.81 kWh total, 15.07 kWh per valid-energy session. Monthly energy/day ranges from 3,327.97 kWh in 2024-09 to 4,929.07 kWh in 2025-04. Full energy belongs to the session-start period, not measured hourly grid load.

Capacity and active-charger-energy concerns each flag 0 sessions; the union is 0. Sensitivity retains all 200,000 sessions (100%) and 3,014,172.81 kWh (100% of baseline). No comparison chart is exported because nothing is excluded; flag counts are reported as validation. This does not verify real measurements: this is synthetic consistency, not corrected/ground-truth data.

Preparation, existing temporal analysis, tests and all three notebooks are rerun for this dataset migration. [Findings](member2_findings.md), [migration/Power BI requirements](dataset_migration.md), [dictionary](data_dictionary.md) and [handoff](team_handoff.md) describe the current contract. Station comparisons, new arrival/active-power charts and Power BI implementation are outside this migration.


The temporal module now includes location-hour percentages, complete-calendar weekday variability, start-period energy/session and charger-type energy/active/connected comparisons, with five reusable CSVs and inline charts in both analysis notebooks. Current exports are ten PNG-only charts; uniform false plausibility flags are reported as validation, not a sensitivity comparison.

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

Source status: **shared by team member; original source and licence unverified**. Collection methodology and timezone are also unverified. Do not describe the dataset as verified real-world or confirmed synthetic. Preserve timezone-naive values until evidence supports a timezone.

Phase 1 reports inconsistent station-ID/name/city/state mappings. Do not guess corrections; station-ID comparisons are conditional on identifier reliability. Avoid geographic recommendations based on these mappings. Supplied `Peak_Hour` labels are not proof of observed demand peaks. Report nearly uniform demand honestly if the calculations show it.

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
| 3 | Verified charts, notebooks and findings | Member 2 seven figures (PNG/SVG), executed analysis notebook and concise findings completed; figures visually inspected. |
| 4 | Power BI integration and end-to-end verification | Planned; no Power BI artifact present. |
| 5 | Individual one-page write-up, README, GitHub cleanup and demo | Planned; README covers scope, preparation, temporal analysis, plotting and notebook commands. |

The existing [quality report](../outputs/data_quality/quality_report.json) reports **200,000 input = 0 exact duplicates removed + 0 rejected + 200,000 accepted**. It reports zero missing values, repeated session-ID groups, invalid timestamps, end-before-start errors, duration mismatches and weekday/month mismatches. All **1,000 station IDs** have multiple names, cities and states, flagging **200,000 rows** without correcting mappings. Its before/after SHA-256 values match. Acceptance establishes identity/timestamp usability under implemented checks, not validity of every measurement.

The extended preparation pipeline and `notebooks/01_preprocessing.ipynb` have been executed. Accepted session starts range from **01-01-2024 00:00 to 30-12-2025 23:53**, covering 730 inclusive dates, all observed. Future averages assume complete collection across that range including zero-session dates; timestamps do not verify uptime or complete boundary days/months.

Energy and queue time each have 200,000 numerically valid values and zero invalid statuses. Separate plausibility concerns flag 49,101 sessions above battery capacity and 71,740 above nominal charger power × calculated elapsed hours. These overlapping concerns cause no exclusion: field definitions, losses and equipment information are unverified. Derived time fields are always recomputed from explicitly parsed timestamps, replacing supplied feature values; original timestamps retain their format.

**Phase 1 handoff:** derived features, preprocessing notebook, documented coverage assumption and measurement-validity policies are implemented. Original source/licence, methodology, timezone and trustworthy station mappings remain unresolved external evidence limitations; do not invent confirmations. Queue quantile choices, station work and Power BI remain later work. See the [data dictionary](data_dictionary.md) for exact feature and flag semantics.


**Phase 2 — Member 2 calculations:** `src/demand_analysis.py` is implemented and executed; see [demand methodology](demand_methodology.md). All six tables independently reconcile 200,000 demand/valid-energy sessions and 9,493,219.61 kWh. Hourly index = hourly average sessions/day divided by the mean of all 24 hourly averages; observed range 0.97668–1.01760 indicates a nearly uniform profile. All busiest/lowest ties are recorded using calendar-normalized demand. December 2025 is a partial boundary month. Sensitivity excludes the union of 97,353 flagged sessions (23,488 flagged by both checks), retaining 3,648,439.11 kWh without changing baseline demand. Raw and cleaned hashes are unchanged. No station/queue analysis, charts, new notebook or Power BI was added in this step.


**Phase 3 — Member 2 presentation:** `src/demand_visualization.py` reads verified summaries and exports seven figures in PNG (300 dpi) and SVG. `notebooks/02_demand_analysis.ipynb` imports existing functions, checks the saved tables against cleaned-data calculations, displays linked figures and compact tables, and explains interpretations/limitations. See [Member 2 findings](member2_findings.md). All rendered figures were inspected; input/Phase 2 hashes are preserved. No station/queue analysis, Power BI or final individual write-up is implemented here.

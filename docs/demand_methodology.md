# Temporal demand and recorded-energy methodology

Member 2's `src/demand_analysis.py` reads `data/processed/charging_sessions.csv` without modifying it. This phase exports calculations only: no station comparisons, queue analysis, charts, Power BI or additional notebook.

## Validation and eligibility

Required columns are `Session_ID`, `Session_Start`, `Energy_Delivered_kWh`, `Energy_Delivered_kWh_Validity`, `Energy_Exceeds_Battery_Capacity` and `Energy_Exceeds_Nominal_Charger_Energy`. Input must be nonempty, IDs unique and nonblank, and every start timestamp valid under explicit `DD-MM-YYYY HH:MM` parsing. Malformed identity, timestamp, schema, quality labels or boolean values fail clearly. IDs retain Phase 1's exact-text identity policy.

Calendar fields used by the analysis are always recomputed from parsed starts; supplied temporal features, including `Is_Weekend`, are not trusted or modified. Timezone remains unverified. The existing preparation parser, numeric-status classifier, coverage helper and SHA-256 helper are reused; Phase 1 code and outputs are preserved.

Energy eligibility is revalidated: finite numeric kWh >= 0, including zero. Missing, nonnumeric, nonfinite and negative values are excluded only from energy calculations, never from demand. Original energy status must be a documented label; disagreements with revalidation are counted, and recomputed eligibility governs calculations. Missing energy is not zero. Exported plausibility flags are parsed explicitly as `True`, `False` or blank (case-insensitive, surrounding whitespace allowed); `"False"` is never converted by Python string truthiness. Blank means not evaluable.

## Calendar and formulas

Build every date from earliest through latest session-start date, inclusive. Future calendar averages assume complete collection across this range, including zero-session dates. This is an assumption, not verified collection uptime. First/last days may be partly observed even if the first timestamp is midnight. Separate year-months are retained; `is_partial_boundary_month` is true when represented dates do not cover the full calendar month. False does not certify collection completeness.

For a group, let N = session count, D = represented calendar days, V = valid-energy session count, and E = sum of valid recorded session energy in kWh:

- `session_count` = N; `calendar_days` = D; `avg_sessions_per_day` = N / D.
- `valid_energy_session_count` = V; `invalid_energy_session_count` = N − V.
- `total_recorded_energy_kwh` = E, provided V > 0.
- `avg_recorded_energy_per_valid_session_kwh` = E / V.
- `avg_recorded_energy_per_day_kwh` = E / D.

No-session groups have zero counts and zero average demand when D > 0. If D = 0 (for example, a weekend category absent from a short calendar), its demand average is undefined rather than an invented rate. Energy totals/averages stay missing if V = 0, even in no-session groups. `energy_observation_status` distinguishes `no_sessions`, `no_valid_energy` and `valid_energy_observed`. Genuine recorded zero energy with V > 0 has a measured total of zero. Undefined values are blank in CSV and null in JSON. Calculations retain floating-point precision; presentation rounding does not affect exported calculations.

## Six summary tables

All tables contain the eight N/D/V/E fields above plus `energy_observation_status`.

- `hourly_demand.csv`: `Charging_Hour` 0–23, all 24 rows. Each hour uses all D dates. Also contains `relative_demand_index`.
- `daily_demand.csv`: `Charging_Date` (`YYYY-MM-DD`), every represented date, D = 1.
- `weekday_demand.csv`: `Weekday_Index` (Monday=0 to Sunday=6) and full English `Weekday_Name`, all seven rows. D counts occurrences of that weekday in the calendar.
- `weekday_weekend_demand.csv`: `Day_Type`, ordered Weekday then Weekend; D counts each type's calendar dates.
- `day_hour_demand.csv`: weekday index/name and hour, ordered Monday 00 through Sunday 23, all 168 combinations. Each D counts that weekday's dates, not all dates and not observed-session dates.
- `monthly_demand.csv`: chronological `Year_Month` (`YYYY-MM`), including zero-session months, with D equal to represented dates in that month and the partial-boundary flag.

Full session energy is attributed to session-start date/hour, including sessions crossing midnight or months. These are energy totals associated with sessions starting then, **not measured hourly electricity-load profiles**. Session-end times and active charging profiles are not reconstructed.

Hourly relative demand index = hourly average sessions/day / mean of the 24 hourly averages. This is a project-defined relative session-start indicator; 1 is the mean hour. It is not a congestion score. All exact busiest/lowest ties are reported for every table using `avg_sessions_per_day`, excluding categories with no represented dates. Thus monthly rankings normalize for represented month length rather than ranking raw monthly counts. Zero-session periods with D > 0 participate in lowest-period ties. `Peak_Hour` labels are unused.

## Energy sensitivity scenario

`monthly_energy_sensitivity.csv` compares baseline valid energy with a scenario excluding the UNION of true battery-capacity and nominal-charger-energy flags. Overlaps are counted once. Blank flags are retained unless the other flag is true; this is not evidence of physical validity. Baseline eligibility still applies to energy in both subsets.

Fields include year-month, calendar days, partial-boundary flag, unchanged baseline session/valid-energy/invalid-energy counts and energy total; `retained_session_count` and `excluded_session_count` partition all demand rows. For each subset, `*_valid_energy_session_count`, `*_recorded_energy_kwh` and `*_energy_observed_dates` describe eligible measurements and date coverage. `retained_valid_energy_fraction` divides retained valid measurements by baseline valid measurements. `retained_avg_recorded_energy_per_calendar_day_kwh` uses the unchanged represented-date denominator, not just retained observation dates. Missing subset energy remains missing when there are no valid observations, including empty subsets.

This is a sensitivity scenario, **not corrected or ground-truth data**. Exclusions can change sample composition by time, vehicle or equipment. No demand row is removed from the six baseline tables. Field definitions, losses and equipment information are unverified; plausibility flags do not prove bad measurements.

## Verification and limitations

`analysis_summary.json` contains coverage, counts, numeric-status disagreements, individual/overlapping/union flag counts, all period ties, hourly-index range, sensitivity totals, reconciliation and input hashes. It contains aggregates, not full session records, and uses strict JSON null instead of NaN/Infinity.

Each of the six tables independently reconciles session counts, valid and invalid energy counts, and energy totals to input. Energy uses relative tolerance 1e-10 and absolute tolerance 1e-6 kWh. Category order/dimensions and sensitivity row/energy partitions are checked before export. Raw (when supplied/available) and cleaned SHA-256 fingerprints are checked; no input file is written. CSV outputs remain ignored by Git.

Source status: **shared by team member; original source and licence unverified**. Methodology and timezone are unverified. Station mappings are inconsistent; no geographic or station conclusions are drawn here. Session counts do not establish congestion; true utilization needs reliable capacity/availability data. A nearly uniform profile must be reported as such. This module does not establish statistical significance, extrapolate beyond observed coverage or infer missing observations.


## Visualization and notebook layer (Phase 3)

`src/demand_visualization.py` reads the existing verified summaries. It only reshapes the weekday–hour table and calculates a trailing seven-observation daily mean (`min_periods=7`); it does not repeat session aggregations. The first six mean values are missing. Seven figures are saved as PNG at 300 dpi and SVG, with zero-based quantitative axes, Okabe–Ito colors and a sequential viridis heatmap. Hatched/asterisk months identify partial calendar coverage, distinct from missing numeric observations. Sensitivity uses the same calendar denominator and a separate retained-count panel, with sample/date coverage context.

`notebooks/02_demand_analysis.ipynb` validates through existing analysis functions and compares their results with the saved tables without rewriting Phase 2 exports. Figures are referenced by relative Markdown image links to keep notebook outputs small; retain the figures directory when sharing. Stable execution removes timing metadata. [Member 2 findings](member2_findings.md) provides the concise descriptive handoff. Visuals and summaries do not infer causes, statistical significance, congestion thresholds or geographic recommendations.

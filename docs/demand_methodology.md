# Temporal demand and recorded-energy methodology

Member 2's `src/demand_analysis.py` reads `data/processed/charging_sessions.csv` without modifying it. This phase exports calculations only: no station comparisons, queue analysis, charts, Power BI or additional notebook.

## Validation and eligibility

Required columns are `Session_ID`, `Session_Start`, `Session_End`, `Charging_End`, `Location_Type`, `Charger_Type`, `Timezone` (`Asia/Kolkata`), `Energy_Delivered_kWh`, `Energy_Delivered_kWh_Validity`, `Energy_Exceeds_Battery_Capacity` and `Energy_Exceeds_Nominal_Charger_Energy`. Input must be nonempty, IDs unique and nonblank, and every start timestamp valid under explicit `DD-MM-YYYY HH:MM` parsing. Malformed identity, timestamp, schema, quality labels or boolean values fail clearly. IDs retain Phase 1's exact-text identity policy.

Calendar fields used by the analysis are always recomputed from parsed starts; supplied temporal features, including `Is_Weekend`, are not trusted or modified. Explicitly parsed timestamps are localized to Asia/Kolkata, as declared by the synthetic CSV. The existing preparation parser, numeric-status classifier, coverage helper and SHA-256 helper are reused; Phase 1 code and outputs are preserved.

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

This is a sensitivity scenario, **not corrected or ground-truth data**. Exclusions can change sample composition by time, vehicle or equipment. No demand row is removed from the six baseline tables. Generator efficiency/loss and equipment assumptions are undocumented; nominal-power bounds use calculated active charging hours, and plausibility flags do not prove bad measurements.

## Verification and limitations

`analysis_summary.json` contains coverage, counts, numeric-status disagreements, individual/overlapping/union flag counts, all period ties, hourly-index range, sensitivity totals, reconciliation and input hashes. It contains aggregates, not full session records, and uses strict JSON null instead of NaN/Infinity.

Each of the six tables independently reconciles session counts, valid and invalid energy counts, and energy totals to input. Energy uses relative tolerance 1e-10 and absolute tolerance 1e-6 kWh. Category order/dimensions and sensitivity row/energy partitions are checked before export. Raw (when supplied/available) and cleaned SHA-256 fingerprints are checked; no input file is written. CSV outputs remain ignored by Git.

Source: **generated synthetic Indian charging data**, `data/raw/EV_Dataset_India.csv`. Generator code, seed, sampling/loss assumptions and reuse licence are not supplied. Local timezone is Asia/Kolkata. Station mappings are internally checked; no real-world geographic conclusions follow from synthetic consistency. Session counts do not establish congestion; true utilization needs reliable capacity/availability data. Temporal patterns must be described from the regenerated CSV results; the old nearly uniform finding no longer applies. This module does not establish statistical significance, extrapolate beyond observed coverage or infer missing observations.


## Visualization and notebook layer (Phase 3)

`src/demand_visualization.py` reads the existing verified summaries. It only reshapes the weekday–hour table and calculates a trailing seven-observation daily mean (`min_periods=7`); it does not repeat session aggregations. The first six mean values are missing. Ten figures are saved as PNG at 300 dpi for the current dataset, with zero-based quantitative axes, Okabe–Ito colors and a sequential viridis heatmap. Hatched/asterisk months identify partial calendar coverage, distinct from missing numeric observations. When informative, sensitivity uses the same calendar denominator and a separate retained-count panel. Uniform flags are reported as validation rather than a comparison chart.

`notebooks/02_demand_analysis.ipynb` validates through existing analysis functions and compares their results with the saved tables without rewriting Phase 2 exports. Figures are referenced by relative Markdown image links to keep notebook outputs small; retain the figures directory when sharing. Stable execution removes timing metadata. [Member 2 findings](member2_findings.md) provides the concise descriptive handoff. Visuals and summaries do not infer causes, statistical significance, congestion thresholds or geographic recommendations.


## Indian-schema migration

Arrival/area/location/port and active-charging fields are preserved; temporal outputs continue to use Session_Start in Asia/Kolkata. They are neither arrival-demand nor active-power profiles. Preparation now checks nominal energy using Charging_End minus Session_Start; Session_End is port release. Port overlaps are flagged on station-local [start,end) intervals. See [migration notes](dataset_migration.md) and [updated dictionary](data_dictionary.md). No old uptime/revenue/weather/grid fields are fabricated.


## Four additional analyses and Power BI summary grains

- `location_type_hourly.csv`: 4 × 24 rows in Workplace, Residential, Retail, Highway order. `session_count` is location-hour starts; `location_session_count` repeats the location denominator. `session_percentage = 100 * session_count / location_session_count`. Each represented type sums to 100%; absent types have zero counts and undefined percentages, not an invented distribution. Use a common vertical scale across panels.
- `daily_weekday_counts.csv`: one observation per represented date, including zero-session dates, with weekday index/name. `weekday_variability.csv` has Monday–Sunday represented-day counts, total sessions, `q1_sessions`, `median_sessions`, `q3_sessions` using pandas linear interpolation. Boxes use the daily observations, 1.5-IQR whiskers and displayed outliers; this is descriptive variability, not a significance test.
- `time_period_energy.csv`: Overnight [00,06), Morning [06,12), Afternoon [12,17), Evening [17,22), Late night [22,24), in Asia/Kolkata. Report total sessions, valid/invalid energy counts, total kWh, `mean_energy_kwh`, `median_energy_kwh`. All 24 hours belong to exactly one bin. Full-session energy belongs to its start bin; unequal bin durations are acceptable for per-session means, but these are not hourly electricity loads. Empty valid-energy groups retain missing energy statistics.
- `charger_type_comparison.csv`: ordered AC Slow, AC Fast, DC Fast, with demand and valid/invalid energy counts, total/mean/median kWh, valid duration counts, mean/median active and connected minutes, and recorded-duration mismatch counts. Active minutes derive from Charging_End minus Session_Start; connected minutes from Session_End minus Session_Start. Supplied Active_Charging_Duration_Min and Session_Duration_Min, when present, are checked within 0.01 minute. Missing/invalid structural timestamps fail clearly; stale supplied durations are reported and never used to manufacture a category effect. Invalid energy does not exclude otherwise valid duration/demand observations.

These summaries reconcile independently to session counts, valid-energy counts and total energy where applicable; represented weekdays reconcile to calendar length, and within-location percentages sum to 100%. Boxplot observations are not individual charging sessions.

The input is generated synthetic Indian data. Documented contracts include named site/charger contexts, battery/SOC energy consistency, nominal power limits, and separate active versus connected intervals. Generator hourly/location sampling weights, random seed and distributions were not supplied. Location-hour peaks are observed sample patterns; shorter active times at higher nominal charger categories are consistent with the physical bound but do not prove a causal equipment effect or equal vehicle mix. We do not resample/reweight rows or force chart relationships.

Figure exports are PNG only. The existing six distinct baseline charts plus these four comparisons produce ten PNGs for the current data. The sensitivity CSV is always retained, but its chart is included only if both retained and excluded valid-energy samples exist. Currently both plausibility flags are uniformly false, so notebooks report counts as validation. Cleanup is limited to recognized generated chart stems; unrelated files are preserved.

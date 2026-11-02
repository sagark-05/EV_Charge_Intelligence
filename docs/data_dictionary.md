# Data dictionary

Source: `data/raw/EV_Dataset.csv`, **shared by team member; original source and licence unverified**. Collection methodology and timezone are also unverified. Definitions below interpret column labels; units, category meanings and business rules have not been independently verified. Original column names and measurement values are preserved.

- `Session_ID`: session identifier; required and unique after exact deduplication.
- `Station_ID`: station identifier; checked against `Station_Name`, `City`, `State` for multiple nonblank values. No authoritative mapping is available.
- `Station_Name`, `City`, `State`: reported station name and location labels.
- `Latitude`, `Longitude`: reported geographic coordinates (coordinate system unverified).
- `Charger_Type`, `Charger_Power_kW`: reported charger category and rated power in kW.
- `Vehicle_Type`, `Vehicle_Battery_kWh`: vehicle category and battery capacity in kWh.
- `Battery_Level_Start`, `Battery_Level_End`: reported initial/final battery levels (apparently percentages; unverified).
- `Energy_Delivered_kWh`: reported delivered energy in kWh.
- `Session_Start`, `Session_End`: timezone-naive timestamps, strictly `DD-MM-YYYY HH:MM`; valid exports use the same format. Invalid source text remains visible in rejected/flagged exports.
- `Session_Duration_Min`: recorded minutes, compared with end minus start (0.01-minute tolerance); never overwritten.
- `Electricity_Price_per_kWh`, `Session_Cost`: reported price per kWh and session cost; currency unverified.
- `Revenue_USD`: reported revenue labelled USD; business definition unverified.
- `Temperature_C`, `Weather_Condition`: reported Celsius temperature and weather category.
- `Peak_Hour`, `Holiday_Flag`, `Fast_Charging_Flag`, `Maintenance_Flag`: supplied indicators; definitions and encodings unverified.
- `Queue_Time_Min`: reported queue minutes.
- `Payment_Method`, `User_Membership_Type`: supplied payment and membership categories.
- `Customer_Rating`, `Battery_Health_Score`: supplied scores; scale definitions unverified.
- `Station_Uptime_Percentage`, `Renewable_Energy_Percentage`, `Grid_Load_Percentage`: reported percentages; denominators/time windows unverified.
- `Day_of_Week`: English full weekday label, checked against start timestamp.
- `Month`: numeric calendar month, checked against start timestamp.
- `Traffic_Index`: supplied traffic index; scale unverified.
- `Carbon_Saved_kg`: reported carbon savings in kg; calculation unverified.

Added metadata:

- `Source_Row_Number`: original 1-based CSV record number including header (first data record = 2). Present in all exported CSVs.
- `Quality_Reasons`: semicolon-separated issue codes, in rejected and flagged CSVs. `missing_value:FIELD` identifies blank/missing fields; `missing_session_id`, `conflicting_session_id`, `invalid_session_start`, `invalid_session_end`, `end_before_start` cause quarantine. `invalid_recorded_duration`, `duration_mismatch`, `weekday_mismatch`, `month_mismatch`, and `station_multiple:FIELD` only flag records.

## Derived features (accepted records)

Features are always recomputed deterministically from explicitly parsed timestamps, replacing any supplied columns with these names. Other original values/columns are preserved. Supplied feature values do not drive calculations. Exact duplicate/conflicting-ID checks still compare all supplied original fields; rejected/flagged audit exports retain supplied feature values when present. Recompute does not infer timezone.

- `Charging_Date`: session-start date as `YYYY-MM-DD`.
- `Charging_Hour`: integer session-start hour, 0–23.
- `Weekday_Index`: integer session-start weekday, Monday=0 through Sunday=6.
- `Weekday_Name`: full English session-start weekday.
- `Is_Weekend`: boolean, true for Saturday/Sunday starts; CSV exports `True`/`False`.
- `Year_Month`: session-start calendar year-month, `YYYY-MM`, keeping years separate.
- `Calculated_Session_Duration_Min`: end minus start in minutes. This is elapsed connection/session time, not confirmed active charging. Original recorded duration is unchanged.

## Measurement validity and plausibility

`Energy_Delivered_kWh_Validity` (energy in kWh) and `Queue_Time_Min_Validity` (queue in minutes) classify each value as:

- `valid`: finite numeric value >= 0; zero is allowed.
- `missing`: blank/whitespace-only or actual null (including an in-memory null/NaN). CSV reading preserves literal tokens: explicit `NaN` is nonfinite, not missing.
- `nonnumeric`: other text that cannot be parsed as a number.
- `nonfinite`: explicit NaN or positive/negative infinity, including numeric overflow to infinity.
- `negative`: finite numeric value < 0.

Invalid classifications add `Energy_Delivered_kWh:STATUS` or `Queue_Time_Min:STATUS` to `Quality_Reasons`. These flags never reject otherwise valid demand rows or fill missing values with zero. Later energy/queue summaries should select `valid` measurements while retaining all accepted rows for demand. The aggregate report provides separate status counts for deduplicated and accepted rows.

Two nullable boolean plausibility columns are separate from numeric validity:

- `Energy_Exceeds_Battery_Capacity`: valid recorded energy > finite nonnegative `Vehicle_Battery_kWh`.
- `Energy_Exceeds_Nominal_Charger_Energy`: valid recorded energy > finite nonnegative `Charger_Power_kW` × calculated elapsed minutes / 60. Requires valid ordered timestamps and a finite comparison product.

`True` means a concern, `False` means evaluated without that concern, and blank means not evaluable because a comparison input is invalid. True values add `plausibility:COLUMN_NAME` reasons. The report counts concerns and unevaluable comparisons separately. No physical-consistency exclusion, upper cutoff or correction is applied: field definitions, losses, equipment information and active charging duration are unverified. Numeric validity remains `valid` even when plausibility flags are true. Concerns may overlap; do not add their counts to estimate distinct sessions.

## Coverage and report interpretation

The aggregate `coverage` object uses accepted session starts only: earliest/latest timestamps in `DD-MM-YYYY HH:MM`, first/last dates in `YYYY-MM-DD`, inclusive calendar-day count and number of observed session dates. With no accepted records the bounds are null and counts zero.

Future calendar averages assume complete collection across the inclusive range, including zero-session dates. Observed timestamps do not verify collection uptime or complete first/last-day coverage. Separate year-months and disclose partial boundary months; the observed range does not establish complete-month collection. Timezone remains unverified.

All supplied non-derived fields receive missing-value checks. Identity, timestamp, duration, calendar and station checks remain in place; additional numerical ranges/cross-measurement relationships are not certified. Original source data is unchanged. Aggregate JSON contains policies, definitions, counts, coverage bounds and raw SHA-256 values, never full records; row-level audit data stays in ignored CSVs. Multiple reasons can describe a single record, so reason counts do not sum to row totals. See the [project plan](project_plan.md) for later phases.

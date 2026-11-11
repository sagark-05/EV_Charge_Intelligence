# Data dictionary — synthetic Indian charging data

Active source: `data/raw/EV_Dataset_India.csv`, generated synthetic Indian charging sessions supplied by the team. Original generator code, random seed and reuse licence are not supplied. The old `EV_Dataset.csv` is preserved. See [migration notes](dataset_migration.md) for schema changes, validation contracts and Power BI work.

## Original columns (32)

- `Station_ID`, `Station_Name`, `City`, `State`, `Area`: supplied synthetic station identity and named locality. Mappings are validated per station; they do not verify actual sites.
- `Latitude`, `Longitude`: supplied geographic coordinates; checked for mapping consistency, not independently surveyed.
- `Location_Type`: supplied site category; current values are Workplace, Retail, Residential and Highway.
- `Charger_Type`, `Charger_Power_kW`: charger category and nominal power (kW).
- `Port_Count`: positive integer station port capacity; not a per-session additive measurement or verified uptime.
- `Port_ID`: integer 1 through `Port_Count`, local to `Station_ID`; identical port numbers at different stations are separate resources.
- `Arrival_Time`: arrival at the station, before or equal to session start.
- `Session_ID`: required unique session identifier after exact deduplication.
- `Vehicle_Type`, `Vehicle_Battery_kWh`: vehicle category and nominal battery capacity (kWh).
- `Session_Start`: session/port-occupancy start, used for existing temporal demand and energy attribution.
- `Charging_End`: end of active charging, between start and session end.
- `Session_End`: end of port occupancy/release; may be later than charging end.
- `Session_Duration_Min`: recorded port occupancy minutes, checked against end minus start.
- `Active_Charging_Duration_Min`: recorded active minutes, checked against charging end minus start.
- `Queue_Time_Min`: recorded queue minutes, checked against start minus arrival.
- `Timezone`: required `Asia/Kolkata`. All four timestamp columns are explicitly parsed as `DD-MM-YYYY HH:MM` and localized there; exports retain that format plus this column. No UTC conversion or timezone inference is performed.
- `Battery_Level_Start`, `Battery_Level_End`: percentages, constrained to 0–100 and nondecreasing.
- `Energy_Delivered_kWh`: recorded energy, compared with battery capacity, battery percentage increase and nominal power × calculated active hours.
- `Electricity_Price_per_kWh`, `Session_Cost`: supplied tariff and session cost; currency is not named in the schema, so confirm it before labelling Power BI currency measures.
- `Fast_Charging_Flag`: supplied indicator; no independent equipment certification implied.
- `Peak_Hour`: supplied label; unused for observed peak identification.
- `Day_of_Week`, `Month`: English full weekday and numeric month, checked against local session start.

## Derived and audit columns

All derived columns are deterministically recomputed on accepted records, replacing any supplied values with those names. Original non-derived columns/values remain intact. Exact deduplication compares all original input fields and keeps the first occurrence. Remaining conflicting session-ID records are all quarantined.

- `Charging_Date`: local start date, `YYYY-MM-DD`.
- `Charging_Hour`: start hour 0–23; `Weekday_Index`: Monday=0 through Sunday=6; `Weekday_Name`: full English name; `Is_Weekend`: boolean Saturday/Sunday; `Year_Month`: `YYYY-MM`.
- `Calculated_Session_Duration_Min`: end minus start (port occupancy minutes).
- `Arrival_Date`, `Arrival_Hour`: local arrival date (`YYYY-MM-DD`) and hour 0–23, separate from session-start demand.
- `Calculated_Queue_Time_Min`: start minus arrival, in minutes.
- `Calculated_Active_Charging_Duration_Min`: charging end minus start, in minutes.
- `Post_Charging_Occupancy_Min`: end minus charging end, in minutes.
- `Station_Port_Key`: original station ID and port ID joined with `/`. Overlap matching canonicalizes numeric port spellings internally; source port text is preserved.
- `Source_Row_Number`: original CSV record number including header (first data record=2), present in all CSV exports.
- `Quality_Reasons`: semicolon-separated reasons in local flagged/rejected exports.
- `Port_Overlap_Flag`: boolean, true for every participant in a positive-duration overlapping occupancy interval on the same station/port. Intervals are `[start,end)`; touching endpoints are allowed. A running maximum catches nested intervals. Overlaps are flagged, not silently removed.

## Validity and flag policies

`Energy_Delivered_kWh_Validity` and `Queue_Time_Min_Validity` are `valid` for finite numeric values >= 0 (zero allowed), `missing` for blanks/nulls, `nonnumeric` for other unparseable text, `nonfinite` for explicit NaN/infinity (including numeric overflow), or `negative`. CSV reading preserves literal `NaN` as nonfinite, not blank. Reasons use `COLUMN:STATUS`; missing values are never zero-filled. Invalid measurements do not remove otherwise usable demand rows.

`Energy_Exceeds_Battery_Capacity` and `Energy_Exceeds_Nominal_Charger_Energy` are nullable booleans. The latter compares valid energy to nominal kW × **calculated active charging minutes** / 60. True adds `plausibility:COLUMN`; false means evaluated without that concern; blank means not evaluable. Comparison tolerance is 1e-6 kWh. These concerns do not automatically invalidate numeric eligibility or correct data. The sensitivity scenario excludes the union of true flags while preserving baseline demand counts.

Other flags: `duration_mismatch`, `active_charging_duration_mismatch`, `queue_time_mismatch` (0.01 minute); `invalid_recorded_duration`, `invalid_active_charging_duration`, `invalid_battery_levels`, `invalid_battery_capacity`, `invalid_charger_power`; `energy_battery_delta_mismatch` (capacity × percentage increase differs by >0.01 kWh plus floating-point tolerance); `weekday_mismatch`, `month_mismatch`; `station_multiple:FIELD`; `missing_value:FIELD`; `overlapping_port_session`. Flags preserve source values.

Quarantine reasons: `missing_session_id`, `conflicting_session_id`, `missing_station_id`, invalid start/end/arrival/charging-end timestamps, `end_before_start`, `arrival_after_session_start`, `charging_end_outside_session`, `invalid_timezone`, `invalid_port_assignment`. Port count/ID must be finite nonnegative integers >=1 with ID <= count. Station mapping checks cover name, city, state, area, location type, coordinates, port count, charger type and power, including deduplicated rejected records.

## Coverage and limitations

Coverage uses accepted session starts only: earliest/latest local timestamps, inclusive first/last dates and calendar-day count; empty accepted data has null bounds and zero counts. Calendar averages assume complete collection across that range, including zero-session dates. Observed timestamps do not verify completeness or full first/last-day coverage. Partial boundary months remain labelled; years are never combined silently.

Generated synthetic consistency is not validation of actual Indian infrastructure or behavior. Full session energy is assigned to its start period, not measured hourly grid load. Occupancy, active charging, arrivals, starts and queues are separate measurements. Generator distributions/loss assumptions and reuse licence remain undocumented. Aggregate JSON reports contain counts, definitions, coverage and hashes rather than full rows; local CSVs carry row-level audit data. See [demand methodology](demand_methodology.md).

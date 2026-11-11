# Indian synthetic dataset migration

Active input: `data/raw/EV_Dataset_India.csv` (200,000 rows, 32 original columns). The original `data/raw/EV_Dataset.csv` is retained unchanged as a legacy input; it does not satisfy the new required preparation schema. No branch, commit or remote change is part of this migration.

Added columns: `Area`, `Location_Type`, `Port_Count`, `Arrival_Time`, `Charging_End`, `Port_ID`, `Active_Charging_Duration_Min`, `Timezone`. Removed columns: `Temperature_C`, `Weather_Condition`, `Payment_Method`, `Customer_Rating`, `Revenue_USD`, `Maintenance_Flag`, `Station_Uptime_Percentage`, `Holiday_Flag`, `Traffic_Index`, `Renewable_Energy_Percentage`, `Carbon_Saved_kg`, `Grid_Load_Percentage`, `User_Membership_Type`, `Battery_Health_Score`. Common session/energy/calendar column names are retained. Removed measurements are not fabricated or imputed.

The preparation default, analysis raw-fingerprint default, notebook input paths, validation fixtures, field documentation, findings and visual annotations are affected. Existing temporal tables still measure **session starts**, not arrivals or active charging profiles; their calculation formulas and reconciliation remain in place.

## Synthetic assumptions and validation

The team identifies this as **generated synthetic Indian charging data**, not observed charging transactions. The CSV declares `Asia/Kolkata`; each timestamp is parsed exactly as `DD-MM-YYYY HH:MM` and localized there. Exports retain that format and the `Timezone` column. No UTC conversion or location-based timezone guess is performed.

The schema models arrival, session start, charging end and port release separately: arrival <= start <= charging end <= session end. `Port_ID` is a station-local integer from 1 through `Port_Count`; location types present are Workplace, Retail, Residential and Highway. Station names, cities, states, areas, coordinates, location types, counts and charger specifications are checked for consistent mapping within `Station_ID`. These checks do not establish real station availability or verified real-world locations.

Recorded queue, active and occupancy minutes are compared with timestamp differences (0.01-minute tolerance). Finite nonnegative recorded energy/queue values are eligible for their metrics. Battery levels must be 0–100 and nondecreasing; recorded energy is checked against battery capacity and battery-capacity × percentage-point increase (0.01 kWh tolerance). The nominal energy limit uses charger kW × **calculated active charging hours**, not total port occupancy (1e-6 kWh comparison tolerance). Plausibility concerns remain flags, separate from numeric validity.

No overlapping occupancy intervals `[Session_Start, Session_End)` are expected on a station/port pair. Touching endpoints are allowed. The running-maximum interval check flags every overlapping participant, including nested intervals; it does not choose a winner. Invalid identity, timezone, port assignment or structural timestamp order is quarantined; measurement mismatches, mappings and overlaps are flagged without arbitrary correction.

Generator code, random seed, sampling distributions, efficiency/loss assumptions and reuse licence were not supplied. The modeled relationships above are CSV contracts checked by this project, not a reconstruction of undocumented generator internals. Temporal differences in this generated sample must not be described as measured Indian consumer behavior.

## Power BI migration still required

Refresh the model from the regenerated `data/processed/charging_sessions.csv`. Remove or repair queries/measures referring to deleted fields; do not retain the previous uptime, revenue, weather, rating or grid/carbon measures as if supplied. Add area/location-type filters and a station dimension from consistent mappings. Use `(Station_ID, Port_ID)` together as port identity; `Port_Count` is station-level and must not be summed once per session. Deduplicate station counts before capacity calculations, and do not treat port counts as verified operational availability.

Treat `Arrival_Time` as arrival demand, `Session_Start` as occupancy start, `Charging_End` as active charging end and `Session_End` as port release. Use the separate calculated duration/queue/post-charge fields and `Port_Overlap_Flag`; do not label occupancy as active charging. Parse wall-time strings day-first as Asia/Kolkata, avoiding implicit Power Query/browser-local conversion. Rebuild the date table from current accepted coverage and reconcile measures with regenerated Python tables under matching filters. Keep the energy-sensitivity scenario separate; no Power BI files were available to update or verify here.

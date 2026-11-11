# Temporal demand and energy findings — Indian synthetic dataset

**Sagar K, PES2UG24CS424.** Active input: `data/raw/EV_Dataset_India.csv` (200,000 sessions, 32 original columns).

Accepted session starts span 01-01-2024 01:53 to 30-12-2025 23:53 in Asia/Kolkata, across 730 inclusive dates. Complete collection including zero-session dates is an assumption; timestamps do not establish uptime or complete boundary-day observation.

Hourly demand is no longer nearly uniform: relative index 0.10560–2.06376. Hour 09 has the most starts (17,198; 23.56/calendar day), versus hour 01 (880; 1.21/day). This is the generated sample's pattern, not evidence of real congestion or actual Indian charging behavior.

Daily starts peak at 377 on 2025-04-02 and are lowest at 186 on 2024-09-28, 2024-10-15. The trailing 7-day mean requires seven observations; the first six values remain missing.

Weekdays average 277.05 starts/day across 522 dates; weekends average 266.25 across 208 dates. Wednesday is highest (280.02/day); Saturday is lowest (265.68/day). Comparisons use each group's calendar denominator; no significance or causes are inferred.

Weekday–hour rates range from 1.01 at Thursday 02:00 to 26.19 at Tuesday 09:00. Higher starts do not measure simultaneous occupancy or prove congestion.

Monthly starts/day range from 220.93 in 2024-09 to 326.17 in 2025-04. Partial boundary months: 2025-12. Partial coverage is not a missing-data marker; the synthetic differences do not establish real seasonality or a causal trend.

All 200,000 energy measurements are numerically valid: 3,014,172.81 kWh total, 15.07 kWh per valid-energy session. Monthly energy/day ranges from 3,327.97 kWh in 2024-09 to 4,929.07 kWh in 2025-04. Full energy belongs to the session-start period, not measured hourly grid load.

Capacity and active-charger-energy concerns each flag 0 sessions; the union is 0. Sensitivity retains all 200,000 sessions (100%) and 3,014,172.81 kWh (100% of baseline). No comparison chart is exported because nothing is excluded; flag counts are reported as validation. This does not verify real measurements: this is synthetic consistency, not corrected/ground-truth data.

Preprocessing found zero rejected records, duplicates, flags, station-mapping conflicts or overlapping station/port intervals. Recorded queue, occupancy and active minutes match their timestamp differences; energy is within battery and active-power limits. The input is generated synthetic Indian charging data. Station mappings are internally consistent in this run, not independently verified locations. Generator code, seed, distribution/efficiency assumptions and reuse licence were not supplied. Keep arrivals, active charging and port occupancy separate. Counts alone do not prove congestion; port counts do not establish operational availability.

Baek, Lee & Kim (2024), [Scientific Data 11, 262](https://doi.org/10.1038/s41597-024-02942-9), motivates temporal inspection; its dataset is separate from this generated CSV and does not prove these results. Calendar normalization and the relative demand index remain project choices.

Member 4 should refresh session-level data and the date table, use these summaries as matching-filter checks, and update removed fields/port and duration semantics described in [migration notes](dataset_migration.md). No Power BI artifacts were available for validation. See [methodology](demand_methodology.md) and [team handoff](team_handoff.md).


## Additional calculated comparisons

**Location-type hourly profiles:** Highway: 18:00, 7.28% (2,611/35,845 sessions); Residential: 19:00, 14.23% (5,378/37,802 sessions); Retail: 18:00, 11.79% (6,775/57,478 sessions); Workplace: 09:00, 16.72% (11,514/68,875 sessions). Workplace/Residential/Retail/Highway are supplied synthetic site contexts. The morning Workplace and evening Residential/Retail peaks describe the CSV. Generator hourly weights were not provided, so no exact generation probabilities, real commuting behavior or causes are asserted.

**Weekday variability:** Daily medians: Monday 277, Tuesday 278, Wednesday 277, Thursday 278.5, Friday 277, Saturday 266.5, Sunday 264. Monday and Tuesday each have 105 represented dates; other weekdays have 104. Quartiles and counts are in weekday_variability.csv; zero dates are retained. Calendar normalization removes unequal weekday representation; the boxplot exposes day-to-day spread rather than only group averages. Complete collection over the range is assumed, not measured uptime; no significance test is claimed.

**Time-period energy per session:** Mean/median kWh per valid-energy session: Overnight 15.01/13.20 (n=8,855); Morning 15.11/13.50 (n=76,931); Afternoon 15.05/13.20 (n=42,513); Evening 15.05/13.20 (n=63,634); Late night 15.08/13.50 (n=8,067). Similar per-session energies coexist with different period session volumes. The simulation contract ties energy to battery/SOC quantities and active-power limits, not to our chart period labels. No time-of-day energy relationship was imposed by this analysis.

**Charger-type comparison:** AC Slow: n=28,764, mean energy 15.07 kWh, mean active 274.19 min, mean connected 352.48 min; AC Fast: n=94,977, mean energy 15.09 kWh, mean active 80.53 min, mean connected 146.39 min; DC Fast: n=76,259, mean energy 15.05 kWh, mean active 29.76 min, mean connected 48.23 min. Supplied active/connected duration mismatch counts are zero. The documented synthetic contract separates active charging from post-charge occupancy and bounds energy by nominal power times active hours. Shorter DC Fast active times are consistent with that contract; similar energy means do not imply a causal charger effect or identical vehicle/sample composition.

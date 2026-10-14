# Data dictionary and metric contract

## Dataset grain and default cohort

`data/raw/bookings.csv` preserves 20,000 source rows and 28 source columns. `data/processed/bookings_clean.csv` contains **19,301 accepted booking IDs**, one row per ID, and 42 columns. All source statuses remain. It is an accepted analytical cohort, not an error-free operational dataset.

The deterministic policy removes one identical duplicate occurrence, then quarantines all 698 records belonging to 349 IDs with conflicting booking dates. No date version is chosen arbitrarily. Separately, 11,408 accepted records have travel before booking; they remain flagged in descriptive analyses. Only 7,893 records enter valid lead-time statistics.

Field names use lower snake case in accepted outputs. Values are trimmed; `Total_Revenue_INR` is renamed `booking_value_inr` to avoid overstating what it measures. Currency is INR. Dates are calendar dates; timezone and extraction timestamp are unspecified.

## Accepted booking fields

| Field | Type / unit | Source | Definition and caveat |
|---|---|---|---|
| `booking_id` | Text | `Booking_ID` | Booking identifier; unique in accepted data. Conflicting identities are quarantined in full. |
| `user_id` | Text | `User_ID` | Supplied user identifier. Distinct users in this file do not equal platform registrations. |
| `booking_date` | ISO date | `Booking_Date` | Reported booking calendar date; primary date basis for monthly analysis. |
| `booking_time` | HH:MM:SS | `Booking_Time` | Reported booking clock time. No timezone supplied. |
| `travel_date` | ISO date | `Travel_Date` | Reported travel date. Negative chronology is flagged, not repaired. |
| `train_number` | Text ID | `Train_Number` | Supplied train number; represented as an identifier. Not a validated service-run key. |
| `train_name` | Text | `Train_Name` | Name as recorded on the booking. Conflicts within each train number. |
| `train_type` | Text | `Train_Type` | Supplied type; consistent within train number in this sample. |
| `railway_zone` | Text | `Railway_Zone` | Supplied route-zone label; may name more than one zone. No independent validation. |
| `source_station` | Text | `Source_Station` | Supplied origin label, including station code and city. |
| `destination_station` | Text | `Destination_Station` | Supplied destination label, including code and city. |
| `route` | Text | `Route` | Supplied origin-destination route label; eight values. Whitespace is stripped. |
| `distance_km` | Integer km | `Distance_KM` | Supplied route distance; not independently geospatially verified. |
| `travel_class` | Category | `Travel_Class` | Supplied class code: 1A, 2A, 3A, CC, EC or SL. Retain codes as supplied. |
| `booking_type` | Category | `Booking_Type` | Reserved, Tatkal or Premium Tatkal. |
| `booking_channel` | Category | `Booking_Channel` | IRCTC Website, IRCTC App or Authorised Partners. |
| `partner_platform` | Category | `Partner_Platform` | Direct IRCTC or supplied intermediary label; distinct from booking channel. |
| `passenger_count` | Positive integer | `Passenger_Count` | Recorded passengers attached to a booking. Includes every retained status; not passengers carried. |
| `base_fare_inr` | Integer INR | `Base_Fare_INR` | Recorded base-fare component per booking; do not multiply again by passenger count. |
| `surge_tatkal_charges_inr` | Integer INR | `Surge_Tatkal_Charges_INR` | Recorded surcharge component per booking; nonnegative. |
| `catering_charges_inr` | Integer INR | `Catering_Charges_INR` | Recorded catering-charge component per booking; nonnegative. |
| `taxes_and_convenience_inr` | Integer INR | `Taxes_And_Convenience_INR` | Recorded combined taxes/convenience component per booking; nonnegative. |
| `booking_value_inr` | Integer INR | `Total_Revenue_INR` | Renamed recorded booking value; sum of four charge components. Includes cancelled/waitlisted records, so not realized revenue or profit. |
| `payment_method` | Category | `Payment_Method` | Supplied payment-method label; no settlement outcome is provided. |
| `booking_status` | Category | `Booking_Status` | Confirmed, RAC, Waitlisted (WL) or Cancelled. Snapshot label; history unavailable. |
| `train_capacity` | Positive integer | `Train_Capacity` | Supplied capacity, stable per train number here. Repeated on bookings; summing it would duplicate capacity. |
| `occupancy_percentage` | Decimal percent 0-100 | `Occupancy_Percentage` | Reported record-level occupancy. Its arithmetic mean is booking-weighted; conflicting train/date values prevent service-level load inference. |
| `on_time_delay_mins` | Integer minutes | `On_Time_Delay_Mins` | Reported record-level delay. Its mean is not verified punctuality; values conflict within train/date. |
| `source_row_number` | Integer | `Derived` | CSV file line number, with the header on line 1 and first data record on line 2; audit pointer to raw input. |
| `booking_month` | YYYY-MM | `Derived` | Calendar month of booking_date; text sorts chronologically. |
| `booking_weekday` | Text | `Derived` | Weekday name derived from booking_date. |
| `booking_hour` | Integer 0-23 | `Derived` | Hour extracted from booking_time. |
| `lead_time_days` | Integer days | `Derived` | travel_date minus booking_date; negative values remain visible. |
| `flag_invalid_chronology` | 0/1 flag | `Derived` | 1 when lead_time_days < 0. |
| `valid_lead_time_days` | Nullable integer days | `Derived` | lead_time_days when nonnegative; blank otherwise. It is the only expected nullable accepted field. |
| `charge_components_inr` | Integer INR | `Derived` | Sum of base fare, surcharge, catering and taxes/convenience. |
| `charge_difference_inr` | Integer INR | `Derived` | booking_value_inr minus charge_components_inr; required to be zero. |
| `flag_charge_mismatch` | 0/1 flag | `Derived` | 1 for nonzero charge_difference_inr; no mismatches in this source. |
| `flag_train_metadata_conflict` | 0/1 flag | `Derived` | 1 when train number maps to inconsistent metadata. Every supplied number conflicts on names/routes/zones. |
| `flag_train_date_occupancy_conflict` | 0/1 flag | `Derived` | 1 for a booking in a (train_number, travel_date) group with multiple occupancy values. |
| `flag_train_date_delay_conflict` | 0/1 flag | `Derived` | 1 for a booking in a (train_number, travel_date) group with multiple delay values. |
| `route_key` | Integer key | `Derived` | Deterministic lookup key to dim_route. Use the provided dimension rather than assuming numeric meaning. |

## Database model

`fact_booking` has one accepted booking per primary key. It references `dim_date(date)` for booking and travel dates, `dim_route(route_key)` and `dim_train(train_number)`. Foreign-key and SQLite integrity checks pass.

- **dim_date**: one calendar date per row; year, quarter, numeric/month-name fields, weekday, weekday number and weekend flag. Use booking date as the active analytical relationship; travel date needs an inactive relationship or a role-playing calendar in BI.
- **dim_route**: one supplied route label per key, with its consistent origin, destination, distance and zone.
- **dim_train**: one train number per row, with only train type and capacity. Names, routes and zones cannot be attached as single values: all 540 train numbers have conflicts.
- User, channel, class, partner, status and other categorical attributes remain on the fact. No unsupported user demographics or new entities are invented.

## Metric definitions

| Metric | Exact definition |
|---|---|
| `avg_record_delay_mins` | Arithmetic mean of supplied On_Time_Delay_Mins over booking records. Train-date values conflict, so this is not a verified punctuality measure. |
| `avg_record_occupancy_pct` | Arithmetic mean of Occupancy_Percentage across accepted booking records, equally weighted per booking. Not a measured train-service load factor. |
| `booking_value_inr` | Sum of source Total_Revenue_INR, renamed recorded booking value. Includes Confirmed, RAC, Waitlisted and Cancelled records. Refunds, settlement and recognized revenue are unavailable. |
| `bookings` | Count of accepted booking records; each accepted Booking_ID is unique. |
| `cancellation_rate_pct` | Cancelled accepted records divided by all accepted records. No status-history or refund data are available. |
| `distinct_train_numbers` | Count of distinct supplied Train_Number values; not trains operated or service departures. Numbers map to multiple names and routes. |
| `lead_time` | Travel_Date minus Booking_Date in calendar days. Negative values are retained and flagged; only nonnegative values enter valid lead-time means and medians. |
| `monthly` | Calendar month of Booking_Date, not Travel_Date or a recognized-revenue date. |
| `passengers` | Sum of Passenger_Count across retained booking records, including all statuses; not observed passengers carried. |
| `population` | One accepted booking ID per row, after exact-row deduplication and quarantine of every member of conflicting booking-ID groups. All statuses are retained. |
| `route` | Route labels and supplied station pair/distance/zone. No independent route validation or geocoding. |
| `total_users` | Distinct supplied User_ID values in the selected accepted booking population; not total registered platform users. |
| `train_dimension` | One row per train number with only consistent type and capacity attributes. Names/routes/zones are retained on facts or route dimension, never arbitrarily chosen for a train number. |

For subgroup averages, recompute from selected records (or weight summary averages by their denominators). Do not average already-aggregated averages without weights. Distinct-user and distinct-train counts are non-additive across groups. Percentages require the selected denominator; a subtotal of shares is valid only for a complete, disjoint partition.

## Audit and companion files

- `exact_duplicates_removed.csv` retains the removed identical occurrence and source position.
- `booking_id_conflicts_quarantine.csv` retains all unresolved identity-conflict members.
- `reconciliation.csv` reconciles source counts and recorded value to accepted totals.
- `summary_*.csv` files aggregate the accepted cohort; their counts and values reconcile to the same baseline.
- `reports/profile.json` records source profile, checksum and policy; `reports/validation.json` holds checks and anomalies; `reports/metrics.json` stores the metric contract and accepted results.

A validation PASS means processing, database and arithmetic controls pass. It does not certify source accuracy or official IRCTC provenance.

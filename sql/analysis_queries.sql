-- IRCTC educational dataset: accepted unique booking IDs; all statuses included.
-- Currency fields are recorded booking value, not recognized/net revenue.
-- Run against data/irctc.sqlite after python src/pipeline.py.

-- Q01. What is the accepted booking population and recorded value?
SELECT COUNT(*) AS bookings,
       SUM(booking_value_inr) AS recorded_booking_value_inr,
       SUM(passenger_count) AS recorded_passengers,
       COUNT(DISTINCT user_id) AS distinct_users,
       COUNT(DISTINCT train_number) AS distinct_train_numbers,
       ROUND(AVG(booking_value_inr), 2) AS avg_booking_value_inr,
       ROUND(AVG(occupancy_percentage), 2) AS avg_booking_record_occupancy_pct
FROM fact_booking;

-- Q02. How do booking-date volumes and values change month to month?
-- One year of data is insufficient to establish recurring seasonality.
WITH monthly AS (
    SELECT booking_month, COUNT(*) AS bookings, SUM(booking_value_inr) AS booking_value_inr
    FROM fact_booking GROUP BY booking_month
), prior AS (
    SELECT *, LAG(bookings) OVER (ORDER BY booking_month) AS prior_bookings,
              LAG(booking_value_inr) OVER (ORDER BY booking_month) AS prior_value
    FROM monthly
)
SELECT booking_month, bookings, booking_value_inr,
       ROUND(100.0 * (bookings - prior_bookings) / NULLIF(prior_bookings, 0), 2) AS mom_booking_change_pct,
       ROUND(100.0 * (booking_value_inr - prior_value) / NULLIF(prior_value, 0), 2) AS mom_value_change_pct
FROM prior ORDER BY booking_month;

-- Q03. Which routes contribute the most bookings and recorded value?
SELECT route, COUNT(*) AS bookings, SUM(passenger_count) AS recorded_passengers,
       SUM(booking_value_inr) AS booking_value_inr,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_booking), 2) AS booking_share_pct,
       ROUND(100.0 * SUM(booking_value_inr) / (SELECT SUM(booking_value_inr) FROM fact_booking), 2) AS value_share_pct,
       ROUND(AVG(booking_value_inr), 2) AS avg_booking_value_inr
FROM fact_booking GROUP BY route ORDER BY bookings DESC, route;

-- Q04. How does recorded booking value split across channel and booking type?
SELECT booking_channel, booking_type, COUNT(*) AS bookings,
       SUM(booking_value_inr) AS booking_value_inr,
       ROUND(AVG(booking_value_inr), 2) AS avg_booking_value_inr,
       SUM(surge_tatkal_charges_inr) AS surge_tatkal_charges_inr
FROM fact_booking GROUP BY booking_channel, booking_type
ORDER BY booking_channel, booking_type;

-- Q05. How much recorded value is associated with each booking status?
-- Cancelled value is NOT a quantified loss or refund amount.
SELECT booking_status, COUNT(*) AS bookings, SUM(booking_value_inr) AS booking_value_inr,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_booking), 2) AS booking_share_pct
FROM fact_booking GROUP BY booking_status ORDER BY bookings DESC;

-- Q06. What is the observed cancelled-record share by channel?
-- This describes the recorded status, not cancellation timing or causality.
SELECT booking_channel, COUNT(*) AS bookings,
       SUM(CASE WHEN booking_status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_records,
       ROUND(100.0 * SUM(CASE WHEN booking_status = 'Cancelled' THEN 1 ELSE 0 END) / COUNT(*), 2) AS cancelled_record_pct
FROM fact_booking GROUP BY booking_channel ORDER BY cancelled_record_pct DESC;

-- Q07. Which travel classes have the largest recorded value per passenger?
-- Fare comparisons remain confounded by route, distance, booking type and train type.
SELECT travel_class, COUNT(*) AS bookings, SUM(passenger_count) AS recorded_passengers,
       SUM(booking_value_inr) AS booking_value_inr,
       ROUND(1.0 * SUM(booking_value_inr) / SUM(passenger_count), 2) AS value_per_recorded_passenger_inr
FROM fact_booking GROUP BY travel_class ORDER BY value_per_recorded_passenger_inr DESC;

-- Q08. Can every currency component be reconciled?
SELECT SUM(base_fare_inr) AS base_fare_inr,
       SUM(surge_tatkal_charges_inr) AS surge_tatkal_charges_inr,
       SUM(catering_charges_inr) AS catering_charges_inr,
       SUM(taxes_and_convenience_inr) AS taxes_and_convenience_inr,
       SUM(booking_value_inr) AS booking_value_inr,
       SUM(booking_value_inr - base_fare_inr - surge_tatkal_charges_inr - catering_charges_inr - taxes_and_convenience_inr) AS residual_inr
FROM fact_booking;

-- Q09. What is booking lead time only among records with valid chronology?
-- CASE preserves all rows in the denominator and NULL excludes invalid lead times from AVG.
SELECT booking_type, COUNT(*) AS all_bookings,
       SUM(flag_invalid_chronology) AS negative_lead_records,
       COUNT(valid_lead_time_days) AS valid_lead_records,
       ROUND(AVG(valid_lead_time_days), 2) AS avg_valid_lead_time_days,
       MIN(valid_lead_time_days) AS min_valid_lead_days,
       MAX(valid_lead_time_days) AS max_valid_lead_days
FROM fact_booking GROUP BY booking_type ORDER BY booking_type;

-- Q10. How are chronology anomalies distributed by booking month?
SELECT booking_month, COUNT(*) AS bookings, SUM(flag_invalid_chronology) AS negative_lead_records,
       ROUND(100.0 * SUM(flag_invalid_chronology) / COUNT(*), 2) AS negative_lead_pct
FROM fact_booking GROUP BY booking_month ORDER BY booking_month;

-- Q11. Does a train number uniquely identify a name/route in this file?
-- Every returned number violates that proposed dimension grain.
SELECT train_number, COUNT(DISTINCT train_name) AS distinct_names,
       COUNT(DISTINCT route) AS distinct_routes, COUNT(DISTINCT railway_zone) AS distinct_zones,
       COUNT(DISTINCT train_type) AS distinct_types, COUNT(DISTINCT train_capacity) AS distinct_capacities
FROM fact_booking GROUP BY train_number
HAVING COUNT(DISTINCT train_name) > 1 OR COUNT(DISTINCT route) > 1
ORDER BY train_number;

-- Q12. How many candidate train-date groups have conflicting operational fields?
-- A train-date is a diagnostic grouping only, not a validated actual-service key.
WITH groups AS (
    SELECT train_number, travel_date, COUNT(*) AS booking_records,
           COUNT(DISTINCT occupancy_percentage) AS occupancy_values,
           COUNT(DISTINCT on_time_delay_mins) AS delay_values
    FROM fact_booking GROUP BY train_number, travel_date
)
SELECT COUNT(*) AS train_date_groups,
       SUM(CASE WHEN booking_records > 1 THEN 1 ELSE 0 END) AS multi_record_groups,
       SUM(CASE WHEN occupancy_values > 1 THEN 1 ELSE 0 END) AS conflicting_occupancy_groups,
       SUM(CASE WHEN delay_values > 1 THEN 1 ELSE 0 END) AS conflicting_delay_groups
FROM groups;

-- Q13. What descriptive mix is recorded by train type?
-- Occupancy/delay are booking-weighted supplied fields, not service performance KPIs.
SELECT train_type, COUNT(*) AS bookings, SUM(booking_value_inr) AS booking_value_inr,
       COUNT(DISTINCT train_number) AS distinct_train_numbers,
       ROUND(AVG(occupancy_percentage), 2) AS avg_booking_record_occupancy_pct,
       ROUND(AVG(on_time_delay_mins), 2) AS avg_booking_record_delay_mins
FROM fact_booking GROUP BY train_type ORDER BY bookings DESC;

-- Q14. What is the observed user-booking frequency in the accepted sample?
-- This is not platform retention or customer lifetime value.
WITH users AS (SELECT user_id, COUNT(*) AS bookings FROM fact_booking GROUP BY user_id)
SELECT bookings AS bookings_per_observed_user, COUNT(*) AS observed_users
FROM users GROUP BY bookings ORDER BY bookings;

-- Q15. Which weekdays and hours contain the most recorded bookings?
SELECT d.weekday_number, d.weekday, f.booking_hour, COUNT(*) AS bookings,
       SUM(f.booking_value_inr) AS booking_value_inr
FROM fact_booking AS f JOIN dim_date AS d ON d.date = f.booking_date
GROUP BY d.weekday_number, d.weekday, f.booking_hour ORDER BY bookings DESC LIMIT 15;

-- Q16. Do dimensional joins multiply or lose any accepted booking records?
SELECT COUNT(*) AS joined_bookings, SUM(f.booking_value_inr) AS joined_booking_value_inr
FROM fact_booking AS f
JOIN dim_train AS t ON f.train_number = t.train_number
JOIN dim_route AS r ON f.route_key = r.route_key
JOIN dim_date AS d ON f.booking_date = d.date;

-- Q17. What descriptive demand and value mix appears by railway-zone label?
SELECT railway_zone, COUNT(*) AS bookings, SUM(booking_value_inr) AS booking_value_inr,
       SUM(passenger_count) AS recorded_passengers
FROM fact_booking GROUP BY railway_zone ORDER BY bookings DESC;

-- Q18. What is the channel mix within each route (rather than overall mix)?
WITH counts AS (
    SELECT route, booking_channel, COUNT(*) AS bookings,
           SUM(booking_value_inr) AS booking_value_inr
    FROM fact_booking GROUP BY route, booking_channel
)
SELECT route, booking_channel, bookings, booking_value_inr,
       ROUND(100.0 * bookings / SUM(bookings) OVER (PARTITION BY route), 2) AS within_route_booking_share_pct
FROM counts ORDER BY route, bookings DESC;

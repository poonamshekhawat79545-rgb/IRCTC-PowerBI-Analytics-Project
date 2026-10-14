#!/usr/bin/env python3
"""Rebuild the IRCTC learning-data analysis using only the Python standard library.

Usage: python src/pipeline.py [--project-root /path/to/project]
Source is immutable; outputs are deterministic for the same CSV bytes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

SCHEMA_VERSION = "1.0"
SOURCE_COLUMNS = [
    "Booking_ID", "User_ID", "Booking_Date", "Booking_Time", "Travel_Date",
    "Train_Number", "Train_Name", "Train_Type", "Railway_Zone", "Source_Station",
    "Destination_Station", "Route", "Distance_KM", "Travel_Class", "Booking_Type",
    "Booking_Channel", "Partner_Platform", "Passenger_Count", "Base_Fare_INR",
    "Surge_Tatkal_Charges_INR", "Catering_Charges_INR", "Taxes_And_Convenience_INR",
    "Total_Revenue_INR", "Payment_Method", "Booking_Status", "Train_Capacity",
    "Occupancy_Percentage", "On_Time_Delay_Mins",
]
RENAME = {name: name.lower() for name in SOURCE_COLUMNS}
RENAME["Total_Revenue_INR"] = "booking_value_inr"
INTEGER_COLUMNS = {
    "distance_km", "passenger_count", "base_fare_inr", "surge_tatkal_charges_inr",
    "catering_charges_inr", "taxes_and_convenience_inr", "booking_value_inr",
    "train_capacity", "on_time_delay_mins",
}
MONEY_COLUMNS = ["base_fare_inr", "surge_tatkal_charges_inr", "catering_charges_inr",
                 "taxes_and_convenience_inr", "booking_value_inr"]
TRAIN_METADATA = ["train_name", "train_type", "railway_zone", "source_station",
                  "destination_station", "route", "distance_km", "train_capacity"]
DEFINITIONS = {
    "population": "One accepted booking ID per row, after exact-row deduplication and quarantine of every member of conflicting booking-ID groups. All statuses are retained.",
    "bookings": "Count of accepted booking records; each accepted Booking_ID is unique.",
    "booking_value_inr": "Sum of source Total_Revenue_INR, renamed recorded booking value. Includes Confirmed, RAC, Waitlisted and Cancelled records. Refunds, settlement and recognized revenue are unavailable.",
    "passengers": "Sum of Passenger_Count across retained booking records, including all statuses; not observed passengers carried.",
    "total_users": "Distinct supplied User_ID values in the selected accepted booking population; not total registered platform users.",
    "distinct_train_numbers": "Count of distinct supplied Train_Number values; not trains operated or service departures. Numbers map to multiple names and routes.",
    "avg_record_occupancy_pct": "Arithmetic mean of Occupancy_Percentage across accepted booking records, equally weighted per booking. Not a measured train-service load factor.",
    "avg_record_delay_mins": "Arithmetic mean of supplied On_Time_Delay_Mins over booking records. Train-date values conflict, so this is not a verified punctuality measure.",
    "lead_time": "Travel_Date minus Booking_Date in calendar days. Negative values are retained and flagged; only nonnegative values enter valid lead-time means and medians.",
    "cancellation_rate_pct": "Cancelled accepted records divided by all accepted records. No status-history or refund data are available.",
    "monthly": "Calendar month of Booking_Date, not Travel_Date or a recognized-revenue date.",
    "route": "Route labels and supplied station pair/distance/zone. No independent route validation or geocoding.",
    "train_dimension": "One row per train number with only consistent type and capacity attributes. Names/routes/zones are retained on facts or route dimension, never arbitrarily chosen for a train number.",
}
POLICIES = {
    "exact_duplicates": "Keep the first occurrence of an identical full source row; save removed occurrences with their source row numbers.",
    "conflicting_booking_ids": "After exact-row deduplication, quarantine ALL rows whose Booking_ID has more than one distinct source record. No row is selected arbitrarily.",
    "chronology": "Retain otherwise accepted rows with booking date after travel date for descriptive booking KPIs; flag and exclude only from valid lead-time analyses.",
    "missing_or_malformed": "Fail immediately on missing required values, malformed dates/time/numbers, nonpositive passenger/capacity values, negative currency/delay/distance, occupancy outside 0-100, or changing source schema.",
    "financial_reconciliation": "Require recorded booking value to equal base fare + surge/Tatkal + catering + taxes/convenience. Fail on mismatch and report count.",
    "operational_fields": "Flag inconsistent train metadata and conflicting train-date occupancy/delay. Retain record-level descriptive values; do not infer service load, punctuality, utilization or actual operated trains.",
    "provenance": "User-supplied educational dataset. No independent evidence that these are official IRCTC production records; findings apply only to this file.",
}


def rounded(value, places=6):
    return round(value, places) if value is not None else None


def write_json(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                               indent=None if compact else 2,
                               separators=(",", ":") if compact else None) + "\n", encoding="utf-8")


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_source(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SOURCE_COLUMNS:
            raise ValueError(f"Unexpected source schema: {reader.fieldnames}")
        rows = []
        for number, row in enumerate(reader, start=2):
            if any(row.get(column) is None or row[column].strip() == "" for column in SOURCE_COLUMNS):
                raise ValueError(f"Missing source value at CSV line {number}")
            if None in row:
                raise ValueError(f"Extra source value at CSV line {number}")
            rows.append({**row, "source_row_number": number})
    if not rows:
        raise ValueError("Source file has no data rows")
    return rows


def partition_rows(rows):
    """Exact dedup first; then quarantine every distinct conflicting-ID member."""
    seen = {}
    distinct, duplicates = [], []
    for row in rows:
        fingerprint = tuple(row[column] for column in SOURCE_COLUMNS)
        if fingerprint in seen:
            duplicates.append({**row, "retained_source_row_number": seen[fingerprint],
                               "exclusion_reason": "exact_duplicate"})
        else:
            seen[fingerprint] = row["source_row_number"]
            distinct.append(row)
    grouped = defaultdict(list)
    for row in distinct:
        grouped[row["Booking_ID"]].append(row)
    conflict_ids = {key for key, values in grouped.items() if len(values) > 1}
    conflict_fields = Counter()
    for key in sorted(conflict_ids):
        for column in SOURCE_COLUMNS:
            if len({row[column] for row in grouped[key]}) > 1:
                conflict_fields[column] += 1
    accepted = [row for row in distinct if row["Booking_ID"] not in conflict_ids]
    quarantine = [{**row, "exclusion_reason": "conflicting_booking_id"}
                  for row in distinct if row["Booking_ID"] in conflict_ids]
    return accepted, duplicates, quarantine, dict(sorted(conflict_fields.items()))


def typed_row(row):
    result = {RENAME[column]: row[column] for column in SOURCE_COLUMNS}
    for key in INTEGER_COLUMNS:
        if not re.fullmatch(r"-?\d+", result[key]):
            raise ValueError(f"Noninteger {key} at line {row['source_row_number']}")
        result[key] = int(result[key])
    result["occupancy_percentage"] = float(result["occupancy_percentage"])
    booking_date = date.fromisoformat(result["booking_date"])
    travel_date = date.fromisoformat(result["travel_date"])
    datetime.strptime(result["booking_time"], "%H:%M:%S")
    if not (0 <= result["occupancy_percentage"] <= 100):
        raise ValueError("Occupancy must be within 0–100")
    if any(result[key] < 0 for key in INTEGER_COLUMNS):
        raise ValueError("Negative numeric source value")
    if result["passenger_count"] <= 0 or result["train_capacity"] <= 0:
        raise ValueError("Nonpositive passenger count or capacity")
    result["source_row_number"] = row["source_row_number"]
    result["booking_month"] = result["booking_date"][:7]
    result["booking_weekday"] = booking_date.strftime("%A")
    result["booking_hour"] = int(result["booking_time"][:2])
    result["lead_time_days"] = (travel_date - booking_date).days
    result["flag_invalid_chronology"] = int(result["lead_time_days"] < 0)
    result["valid_lead_time_days"] = result["lead_time_days"] if result["lead_time_days"] >= 0 else None
    result["charge_components_inr"] = sum(result[key] for key in MONEY_COLUMNS[:-1])
    result["charge_difference_inr"] = result["booking_value_inr"] - result["charge_components_inr"]
    result["flag_charge_mismatch"] = int(result["charge_difference_inr"] != 0)
    return result


def profile_train_fields(rows):
    trains, services = defaultdict(list), defaultdict(list)
    for row in rows:
        trains[row["train_number"]].append(row)
        services[(row["train_number"], row["travel_date"])].append(row)
    field_counts = {column: sum(len({row[column] for row in group}) > 1 for group in trains.values())
                    for column in TRAIN_METADATA}
    bad_trains = {key for key, group in trains.items()
                  if any(len({row[column] for row in group}) > 1 for column in TRAIN_METADATA)}
    occupancy_conflicts = {key for key, group in services.items()
                           if len({row["occupancy_percentage"] for row in group}) > 1}
    delay_conflicts = {key for key, group in services.items()
                      if len({row["on_time_delay_mins"] for row in group}) > 1}
    for row in rows:
        service_key = (row["train_number"], row["travel_date"])
        row["flag_train_metadata_conflict"] = int(row["train_number"] in bad_trains)
        row["flag_train_date_occupancy_conflict"] = int(service_key in occupancy_conflicts)
        row["flag_train_date_delay_conflict"] = int(service_key in delay_conflicts)
    profile = {
        "population": "accepted booking records",
        "train_number_count": len(trains),
        "train_metadata_conflicting_numbers": len(bad_trains),
        "train_metadata_conflicting_numbers_by_field": field_counts,
        "train_date_groups": len(services),
        "train_date_groups_with_multiple_records": sum(len(group) > 1 for group in services.values()),
        "train_date_occupancy_conflicting_groups": len(occupancy_conflicts),
        "train_date_delay_conflicting_groups": len(delay_conflicts),
        "records_in_occupancy_conflicting_groups": sum(row["flag_train_date_occupancy_conflict"] for row in rows),
        "records_in_delay_conflicting_groups": sum(row["flag_train_date_delay_conflict"] for row in rows),
    }
    return profile


def summarize(rows):
    count = len(rows)
    value = sum(row["booking_value_inr"] for row in rows)
    passengers = sum(row["passenger_count"] for row in rows)
    valid_leads = [row["valid_lead_time_days"] for row in rows if row["valid_lead_time_days"] is not None]
    status_counts = Counter(row["booking_status"] for row in rows)
    totals = {
        "row_count": count, "bookings": count, "booking_value_inr": value,
        "passengers": passengers,
        "total_users": len({row["user_id"] for row in rows}),
        "distinct_train_numbers": len({row["train_number"] for row in rows}),
        "route_count": len({row["route"] for row in rows}),
        "avg_booking_value_inr": rounded(value / count) if count else None,
        "value_per_recorded_passenger_inr": rounded(value / passengers) if passengers else None,
        "avg_passengers_per_booking": rounded(passengers / count) if count else None,
        "avg_record_occupancy_pct": rounded(statistics.mean(row["occupancy_percentage"] for row in rows)) if count else None,
        "avg_record_delay_mins": rounded(statistics.mean(row["on_time_delay_mins"] for row in rows)) if count else None,
        "median_record_delay_mins": statistics.median(row["on_time_delay_mins"] for row in rows) if count else None,
        "zero_delay_record_count": sum(row["on_time_delay_mins"] == 0 for row in rows),
        "valid_lead_time_count": len(valid_leads),
        "invalid_chronology_count": count - len(valid_leads),
        "invalid_chronology_pct": rounded(100 * (count - len(valid_leads)) / count) if count else None,
        "avg_valid_lead_time_days": rounded(statistics.mean(valid_leads)) if valid_leads else None,
        "median_valid_lead_time_days": statistics.median(valid_leads) if valid_leads else None,
        "confirmed_count": status_counts["Confirmed"],
        "cancelled_count": status_counts["Cancelled"],
        "cancellation_rate_pct": rounded(100 * status_counts["Cancelled"] / count) if count else None,
        "booking_date_min": min((row["booking_date"] for row in rows), default=None),
        "booking_date_max": max((row["booking_date"] for row in rows), default=None),
        "travel_date_min": min((row["travel_date"] for row in rows), default=None),
        "travel_date_max": max((row["travel_date"] for row in rows), default=None),
    }
    for column in MONEY_COLUMNS[:-1]:
        totals[column] = sum(row[column] for row in rows)
    return totals


def aggregate(rows, fields, descending=False):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    results = [{**dict(zip(fields, key)), **summarize(group)} for key, group in sorted(groups.items())]
    overall_value = sum(row["booking_value_inr"] for row in rows)
    for result in results:
        result["booking_share_pct"] = rounded(100 * result["row_count"] / len(rows)) if rows else None
        result["value_share_pct"] = rounded(100 * result["booking_value_inr"] / overall_value) if overall_value else None
    if descending:
        results.sort(key=lambda row: (-row["row_count"], tuple(row[field] for field in fields)))
    return results


def raw_profile(raw, typed, source_path):
    columns = {}
    for column in SOURCE_COLUMNS:
        values = [row[column] for row in raw]
        counts = Counter(values)
        details = {"distinct_count": len(counts), "missing_count": sum(value.strip() == "" for value in values)}
        if len(counts) <= 60:
            details["value_counts"] = dict(sorted(counts.items()))
        clean_name = RENAME[column]
        if clean_name in INTEGER_COLUMNS or clean_name == "occupancy_percentage":
            numbers = [row[clean_name] for row in typed]
            details.update(min=min(numbers), max=max(numbers), mean=rounded(statistics.mean(numbers)),
                           median=statistics.median(numbers))
        if column in ("Booking_Date", "Travel_Date"):
            details.update(min=min(values), max=max(values))
        columns[column] = details
    return {"schema_version": SCHEMA_VERSION, "source_file": source_path.name,
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "source_rows": len(raw), "source_columns": len(SOURCE_COLUMNS), "columns": columns}


def build_dimensions(rows):
    route_fields = ["route", "source_station", "destination_station", "distance_km", "railway_zone"]
    routes = defaultdict(list)
    trains = defaultdict(list)
    for row in rows:
        routes[row["route"]].append(row)
        trains[row["train_number"]].append(row)
    dim_route = []
    for key, (route, group) in enumerate(sorted(routes.items()), start=1):
        if any(len({row[field] for row in group}) > 1 for field in route_fields):
            raise ValueError(f"Route attributes conflict for {route}; refine route grain before modeling")
        dim_route.append({"route_key": key, **{field: group[0][field] for field in route_fields}})
    keys = {row["route"]: row["route_key"] for row in dim_route}
    for row in rows:
        row["route_key"] = keys[row["route"]]
    dim_train = []
    for number, group in sorted(trains.items()):
        for field in ["train_type", "train_capacity"]:
            if len({row[field] for row in group}) != 1:
                raise ValueError(f"Cannot use {field} in dim_train: inconsistent for {number}")
        dim_train.append({"train_number": number, "train_type": group[0]["train_type"],
                          "train_capacity": group[0]["train_capacity"]})
    calendar = []
    start = min(date.fromisoformat(row[field]) for row in rows for field in ("booking_date", "travel_date"))
    end = max(date.fromisoformat(row[field]) for row in rows for field in ("booking_date", "travel_date"))
    for ordinal in range(start.toordinal(), end.toordinal() + 1):
        day = date.fromordinal(ordinal)
        calendar.append({"date": day.isoformat(), "year": day.year, "quarter": (day.month - 1) // 3 + 1,
                         "month_number": day.month, "month": day.strftime("%Y-%m"),
                         "month_name": day.strftime("%B"), "weekday": day.strftime("%A"),
                         "weekday_number": day.weekday() + 1, "is_weekend": int(day.weekday() >= 5)})
    return dim_route, dim_train, calendar


def build_database(path, rows, dimensions):
    if path.exists():
        path.unlink()
    route, train, calendar = dimensions
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript('''
CREATE TABLE dim_date(date TEXT PRIMARY KEY, year INTEGER NOT NULL, quarter INTEGER NOT NULL,
 month_number INTEGER NOT NULL, month TEXT NOT NULL, month_name TEXT NOT NULL,
 weekday TEXT NOT NULL, weekday_number INTEGER NOT NULL, is_weekend INTEGER NOT NULL);
CREATE TABLE dim_route(route_key INTEGER PRIMARY KEY, route TEXT UNIQUE NOT NULL,
 source_station TEXT NOT NULL, destination_station TEXT NOT NULL,
 distance_km INTEGER NOT NULL, railway_zone TEXT NOT NULL);
CREATE TABLE dim_train(train_number TEXT PRIMARY KEY, train_type TEXT NOT NULL, train_capacity INTEGER NOT NULL);
''')
    for table, values in [("dim_date", calendar), ("dim_route", route), ("dim_train", train)]:
        columns = list(values[0])
        connection.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                               [tuple(row[column] for column in columns) for row in values])
    columns = list(rows[0])
    schema = []
    for column in columns:
        if column == "booking_id":
            schema.append('booking_id TEXT PRIMARY KEY')
        elif column == "occupancy_percentage":
            schema.append(f'{column} REAL NOT NULL CHECK ({column} BETWEEN 0 AND 100)')
        elif column in INTEGER_COLUMNS or column.startswith("flag_") or column in {
                "source_row_number", "booking_hour", "lead_time_days", "valid_lead_time_days",
                "charge_components_inr", "charge_difference_inr", "route_key"}:
            schema.append(f'{column} INTEGER' + ('' if column == 'valid_lead_time_days' else ' NOT NULL'))
        else:
            schema.append(f'{column} TEXT NOT NULL')
    schema += ["FOREIGN KEY(booking_date) REFERENCES dim_date(date)",
               "FOREIGN KEY(travel_date) REFERENCES dim_date(date)",
               "FOREIGN KEY(train_number) REFERENCES dim_train(train_number)",
               "FOREIGN KEY(route_key) REFERENCES dim_route(route_key)",
               "CHECK(passenger_count > 0)", "CHECK(booking_value_inr >= 0)",
               "CHECK(charge_difference_inr = 0)"]
    connection.execute("CREATE TABLE fact_booking (" + ",".join(schema) + ")")
    connection.executemany(f"INSERT INTO fact_booking VALUES ({','.join('?' for _ in columns)})",
                           [tuple(row[column] for column in columns) for row in rows])
    connection.executescript('''
CREATE INDEX idx_booking_date ON fact_booking(booking_date);
CREATE INDEX idx_booking_channel_status ON fact_booking(booking_channel,booking_status);
CREATE INDEX idx_booking_route ON fact_booking(route_key);
CREATE INDEX idx_booking_train_date ON fact_booking(train_number,travel_date);
CREATE VIEW v_monthly AS SELECT booking_month, COUNT(*) row_count, SUM(booking_value_inr) booking_value_inr,
 SUM(passenger_count) passengers, AVG(booking_value_inr) avg_booking_value_inr,
 SUM(flag_invalid_chronology) invalid_chronology_count FROM fact_booking GROUP BY booking_month;
CREATE VIEW v_routes AS SELECT route, COUNT(*) row_count, SUM(booking_value_inr) booking_value_inr,
 SUM(passenger_count) passengers FROM fact_booking GROUP BY route;
CREATE VIEW v_channels AS SELECT booking_channel, COUNT(*) row_count, SUM(booking_value_inr) booking_value_inr,
 SUM(passenger_count) passengers FROM fact_booking GROUP BY booking_channel;
CREATE VIEW v_status AS SELECT booking_status, COUNT(*) row_count, SUM(booking_value_inr) booking_value_inr,
 SUM(passenger_count) passengers FROM fact_booking GROUP BY booking_status;
''')
    connection.commit()
    checks = {
        "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_violations": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
        "sql_row_count": connection.execute("SELECT COUNT(*) FROM fact_booking").fetchone()[0],
        "sql_booking_value_inr": connection.execute("SELECT SUM(booking_value_inr) FROM fact_booking").fetchone()[0],
    }
    ddl = "\n\n".join(sql + ";" for (sql,) in connection.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END,name"))
    connection.close()
    return checks, ddl


def run(root):
    source_path = root / "data/raw/bookings.csv"
    processed = root / "data/processed"
    reports = root / "reports"
    processed.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    (root / "sql").mkdir(parents=True, exist_ok=True)
    raw = read_source(source_path)
    raw_typed = [typed_row(row) for row in raw]  # validates every row, even excluded ones
    charge_mismatches = sum(row["flag_charge_mismatch"] for row in raw_typed)
    if charge_mismatches:
        raise ValueError(f"{charge_mismatches} source records fail charge reconciliation")
    accepted_raw, duplicate_raw, quarantine_raw, conflict_fields = partition_rows(raw)
    rows = sorted((typed_row(row) for row in accepted_raw), key=lambda row: row["booking_id"])
    if not rows:
        raise ValueError("No accepted booking rows remain after identity validation")
    operation_profile = profile_train_fields(rows)
    dimensions = build_dimensions(rows)
    duplicate_value = sum(int(row["Total_Revenue_INR"]) for row in duplicate_raw)
    quarantine_value = sum(int(row["Total_Revenue_INR"]) for row in quarantine_raw)
    raw_value = sum(row["booking_value_inr"] for row in raw_typed)
    totals = summarize(rows)
    quality = {
        "source_row_count": len(raw), "source_unique_booking_ids": len({row['Booking_ID'] for row in raw}),
        "source_booking_value_inr": raw_value,
        "exact_duplicate_rows_removed": len(duplicate_raw), "exact_duplicate_value_removed_inr": duplicate_value,
        "conflicting_booking_id_groups": len({row['Booking_ID'] for row in quarantine_raw}),
        "quarantined_rows": len(quarantine_raw), "quarantined_booking_value_inr": quarantine_value,
        "conflicting_fields_by_group_count": conflict_fields,
        "accepted_row_count": len(rows), "accepted_booking_value_inr": totals["booking_value_inr"],
        "retained_row_pct": rounded(100 * len(rows) / len(raw)),
        "invalid_chronology_count": totals["invalid_chronology_count"],
        "invalid_chronology_pct": totals["invalid_chronology_pct"],
        "valid_lead_time_count": totals["valid_lead_time_count"],
        "source_charge_mismatch_count": charge_mismatches,
        "source_missing_cell_count": sum(row[column].strip() == "" for row in raw for column in SOURCE_COLUMNS),
        **operation_profile,
    }
    aggregations = {
        "monthly": aggregate(rows, ["booking_month"]),
        "routes": aggregate(rows, ["route"], True),
        "channels": aggregate(rows, ["booking_channel"], True),
        "booking_types": aggregate(rows, ["booking_type"], True),
        "statuses": aggregate(rows, ["booking_status"], True),
        "zones": aggregate(rows, ["railway_zone"], True),
        "classes": aggregate(rows, ["travel_class"], True),
        "train_types": aggregate(rows, ["train_type"], True),
        "partners": aggregate(rows, ["partner_platform"], True),
        "payment_methods": aggregate(rows, ["payment_method"], True),
        "channel_type": aggregate(rows, ["booking_channel", "booking_type"]),
        "monthly_channel": aggregate(rows, ["booking_month", "booking_channel"]),
        "monthly_status": aggregate(rows, ["booking_month", "booking_status"]),
        "weekday": aggregate(rows, ["booking_weekday"]),
        "hourly": aggregate(rows, ["booking_hour"]),
    }
    prior = None
    for month in aggregations["monthly"]:
        month["mom_booking_change_pct"] = rounded(100 * (month["row_count"] / prior["row_count"] - 1)) if prior else None
        month["mom_value_change_pct"] = rounded(100 * (month["booking_value_inr"] / prior["booking_value_inr"] - 1)) if prior else None
        prior = month
    top_route = aggregations["routes"][0]
    top_channel = aggregations["channels"][0]
    peak = max(aggregations["monthly"], key=lambda row: row["row_count"])
    tatkal = [row for row in rows if row["booking_type"] in {"Tatkal", "Premium Tatkal"}]
    findings = [
        {"id": "identity_quality", "title": "Identity validation prevents inflated totals",
         "evidence": {"rows_excluded": len(duplicate_raw) + len(quarantine_raw),
                      "booking_value_excluded_inr": duplicate_value + quarantine_value},
         "interpretation": "Conflicting booking dates cannot be resolved from this file; all affected IDs are isolated before reporting."},
        {"id": "chronology", "title": "Chronology limits planning analysis",
         "evidence": {"invalid_records": totals['invalid_chronology_count'], "invalid_pct": totals['invalid_chronology_pct'],
                      "valid_lead_time_records": totals['valid_lead_time_count']},
         "interpretation": "Booking-to-travel lead-time findings apply only to nonnegative records and should not be generalized to all bookings."},
        {"id": "route_mix", "title": "Largest route by booking count",
         "evidence": {key: top_route[key] for key in ['route', 'row_count', 'booking_value_inr', 'booking_share_pct']},
         "interpretation": "Prioritize investigation of high-volume route experience within this sample; validate representative coverage before business action."},
        {"id": "channel_mix", "title": "Largest booking channel",
         "evidence": {key: top_channel[key] for key in ['booking_channel', 'row_count', 'booking_value_inr', 'booking_share_pct']},
         "interpretation": "This is a descriptive channel mix. Conversion, marketing return and channel profitability require additional data."},
        {"id": "monthly_peak", "title": "Peak month of recorded booking demand",
         "evidence": {key: peak[key] for key in ['booking_month', 'row_count', 'booking_value_inr']},
         "interpretation": "One year of booking records establishes a within-sample peak, not a recurring seasonal pattern."},
        {"id": "tatkal_mix", "title": "Tatkal mix and recorded value",
         "evidence": {"row_count": len(tatkal), "booking_share_pct": rounded(100 * len(tatkal) / len(rows)),
                      "booking_value_inr": sum(row['booking_value_inr'] for row in tatkal),
                      "value_share_pct": rounded(100 * sum(row['booking_value_inr'] for row in tatkal) / totals['booking_value_inr'])},
         "interpretation": "Tatkal and Premium Tatkal are combined here. Value differences also reflect passenger counts, distance, class and train-type mix; no causal price effect is identified."},
    ]
    metrics = {"schema_version": SCHEMA_VERSION, "dataset_label": "IRCTC educational booking dataset",
               "source_file": "data/raw/bookings.csv", "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
               "definitions": DEFINITIONS, "policies": POLICIES, "totals": totals,
               "quality": quality, "findings": findings, **aggregations}
    write_csv(processed / "bookings_clean.csv", rows, list(rows[0]))
    write_csv(processed / "exact_duplicates_removed.csv", duplicate_raw,
              SOURCE_COLUMNS + ["source_row_number", "retained_source_row_number", "exclusion_reason"])
    write_csv(processed / "booking_id_conflicts_quarantine.csv", quarantine_raw,
              SOURCE_COLUMNS + ["source_row_number", "exclusion_reason"])
    for name, values in zip(["dim_route", "dim_train", "dim_date"], dimensions):
        write_csv(processed / f"{name}.csv", values, list(values[0]))
    for name, values in aggregations.items():
        write_csv(processed / f"summary_{name}.csv", values, list(values[0]))
    reconciliation = [
        {"stage": "source", "row_count": len(raw), "booking_value_inr": raw_value},
        {"stage": "less_exact_duplicate_occurrences", "row_count": -len(duplicate_raw), "booking_value_inr": -duplicate_value},
        {"stage": "less_conflicting_id_quarantine", "row_count": -len(quarantine_raw), "booking_value_inr": -quarantine_value},
        {"stage": "accepted", "row_count": len(rows), "booking_value_inr": totals['booking_value_inr']},
    ]
    write_csv(processed / "reconciliation.csv", reconciliation, ["stage", "row_count", "booking_value_inr"])
    sql_checks, ddl = build_database(root / "data/irctc.sqlite", rows, dimensions)
    (root / "sql/schema.sql").write_text("-- Generated by src/pipeline.py; use the pipeline to load data.\n" + ddl + "\n", encoding="utf-8")
    validations = {
        "row_count_reconciles": len(raw) == len(rows) + len(duplicate_raw) + len(quarantine_raw),
        "booking_value_reconciles": raw_value == totals["booking_value_inr"] + duplicate_value + quarantine_value,
        "accepted_booking_ids_unique": len(rows) == len({row["booking_id"] for row in rows}),
        "accepted_and_quarantine_ids_disjoint": not ({row['booking_id'] for row in rows} & {row['Booking_ID'] for row in quarantine_raw}),
        "all_charge_components_reconcile": charge_mismatches == 0,
        "lead_time_denominators_reconcile": totals["valid_lead_time_count"] + totals["invalid_chronology_count"] == len(rows),
        "sqlite_integrity_ok": sql_checks["integrity_check"] == "ok",
        "sqlite_foreign_keys_valid": sql_checks["foreign_key_violations"] == 0,
        "sqlite_totals_match": sql_checks["sql_row_count"] == len(rows) and sql_checks["sql_booking_value_inr"] == totals['booking_value_inr'],
    }
    for name, values in aggregations.items():
        validations[f"{name}_count_and_value_reconcile"] = (
            sum(item['row_count'] for item in values) == len(rows)
            and sum(item['booking_value_inr'] for item in values) == totals['booking_value_inr']
            and sum(item['passengers'] for item in values) == totals['passengers'])
    validation = {"schema_version": SCHEMA_VERSION, "status": "PASS" if all(validations.values()) else "FAIL",
                  "check_count": len(validations), "checks": validations, "sql_checks": sql_checks,
                  "reconciliation": reconciliation,
                  "qualification": "PASS means processing and accounting controls pass; source anomalies remain explicitly flagged or quarantined.",
                  "anomalies": quality}
    write_json(reports / "metrics.json", metrics)
    write_json(reports / "validation.json", validation)
    write_json(reports / "profile.json", {**raw_profile(raw, raw_typed, source_path),
                                         "quality": quality, "policies": POLICIES})
    user_keys = {user: key for key, user in enumerate(sorted({row['user_id'] for row in rows}), start=1)}
    dashboard_columns = ["booking_id", "booking_date", "booking_month", "travel_date", "booking_value_inr",
                         "passenger_count", "train_number", "user_key", "occupancy_percentage", "on_time_delay_mins",
                         "route", "booking_type", "booking_channel", "booking_status", "train_type", "railway_zone",
                         "travel_class", "flag_invalid_chronology", "lead_time_days", "valid_lead_time_days",
                         "flag_charge_mismatch", "flag_train_metadata_conflict",
                         "flag_train_date_occupancy_conflict", "flag_train_date_delay_conflict"]
    dashboard_rows = [[user_keys[row['user_id']] if column == 'user_key' else row[column]
                       for column in dashboard_columns] for row in rows]
    write_json(reports / "dashboard_data.json", {
        "schema_version": SCHEMA_VERSION, "population_label": "Accepted unique booking IDs • all statuses",
        "definitions": DEFINITIONS, "columns": dashboard_columns, "rows": dashboard_rows,
        "controls": totals, "quality": quality}, compact=True)
    if not all(validations.values()):
        raise AssertionError("Validation failed; see reports/validation.json")
    print(json.dumps({"status": validation["status"], "checks": len(validations),
                      "accepted_rows": len(rows), "booking_value_inr": totals['booking_value_inr'],
                      "quarantined_rows": len(quarantine_raw), "invalid_chronology": totals['invalid_chronology_count']}, indent=2))
    return metrics, validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    run(arguments.project_root.resolve())

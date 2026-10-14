#!/usr/bin/env python3
"""Build a portable native PBIP semantic model with embedded accepted CSV data.

Uses documented TMSL model.bim + definition.pbism. No Power BI installation is
required to build the text definitions. First refresh and native-engine testing
must still be performed in Power BI Desktop on Windows.
"""
from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import json
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "powerbi/IRCTC.SemanticModel"
PBISM_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json"
NAMESPACE = uuid.UUID("2e24f983-f2ce-5c7c-9f59-88f232ae25ad")
INTEGER_COLUMNS = {
    "distance_km", "passenger_count", "base_fare_inr", "surge_tatkal_charges_inr",
    "catering_charges_inr", "taxes_and_convenience_inr", "booking_value_inr",
    "train_capacity", "on_time_delay_mins", "source_row_number", "booking_hour",
    "lead_time_days", "valid_lead_time_days", "charge_components_inr", "charge_difference_inr",
    "route_key", "flag_invalid_chronology", "flag_charge_mismatch", "flag_train_metadata_conflict",
    "flag_train_date_occupancy_conflict", "flag_train_date_delay_conflict",
}
DATE_COLUMNS = {"booking_date", "travel_date", "date"}
CALENDAR_INTEGERS = {"year", "quarter", "month_number", "weekday_number", "is_weekend"}
HIDDEN_COLUMNS = {"source_row_number", "route_key", "charge_components_inr", "charge_difference_inr"}
SOURCES = [
    "https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset",
    "https://learn.microsoft.com/en-us/analysis-services/tmsl/database-object-tmsl",
    "https://learn.microsoft.com/en-us/analysis-services/tmsl/tables-object-tmsl",
    "https://learn.microsoft.com/en-us/analysis-services/tmsl/relationships-object-tmsl",
    "https://raw.githubusercontent.com/microsoft/mcp/main/tools/Fabric.Mcp.Tools.Docs/src/Resources/item-definitions/semantic-model-definition.md",
    "https://learn.microsoft.com/en-us/powerquery-m/binary-decompress",
    "https://learn.microsoft.com/en-us/powerquery-m/csv-document",
    PBISM_SCHEMA,
]


def lineage(name):
    return str(uuid.uuid5(NAMESPACE, name))


def encode_csv(csv_bytes):
    return base64.b64encode(gzip.compress(csv_bytes, compresslevel=9, mtime=0)).decode("ascii")


def embedded_partition(table_name, csv_bytes, columns, types):
    """Use deterministic gzip/Base64 chunks so no source path or credentials exist."""
    encoded = encode_csv(csv_bytes)
    chunks = [encoded[index:index + 16000] for index in range(0, len(encoded), 16000)]
    lines = [
        "let",
        "    // Portable snapshot: source CSV bytes embedded as GZip + Base64.",
        "    // No File.Contents, Web.Contents, gateway or credentials are needed.",
        "    EmbeddedBase64 = Text.Combine({",
        *["        " + json.dumps(chunk) + ("," if index < len(chunks) - 1 else "")
          for index, chunk in enumerate(chunks)],
        "    }, \"\"),",
        "    CsvBytes = Binary.Decompress(Binary.FromText(EmbeddedBase64, BinaryEncoding.Base64), Compression.GZip),",
        f"    Source = Csv.Document(CsvBytes, [Delimiter=\",\", Columns={len(columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),",
        "    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
    ]
    step = "Headers"
    if "valid_lead_time_days" in columns:
        # Blank means excluded from valid-lead calculations, not zero days.
        lines.append('    MissingLeadAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, {"valid_lead_time_days"}),')
        step = "MissingLeadAsNull"
    lines += [f"    Typed = Table.TransformColumnTypes({step}, {{"]
    lines += ["        {" + json.dumps(column) + ", " + types[column] + "}" + ("," if i < len(columns) - 1 else "")
              for i, column in enumerate(columns)]
    lines += ['    }, "en-US")', "in", "    Typed"]
    return {
        "name": table_name, "mode": "import",
        "source": {"type": "m", "expression": lines},
        "annotations": [
            {"name": "IRCTC_EmbeddedCsvSha256", "value": hashlib.sha256(csv_bytes).hexdigest()},
            {"name": "IRCTC_EmbeddedCsvEncoding", "value": "UTF-8 CSV; GZip; Base64; 16000-character chunks"},
        ],
    }


def decode_partition(partition):
    """Independently recover the exact bytes from the emitted M expression."""
    expression = "\n".join(partition["source"]["expression"])
    body = re.search(r'EmbeddedBase64 = Text.Combine\(\{(.*?)\}, ""\)', expression, re.S).group(1)
    chunks = re.findall(r'"([A-Za-z0-9+/=]+)"', body)
    return gzip.decompress(base64.b64decode("".join(chunks), validate=True))


def m_type(column):
    if column in DATE_COLUMNS:
        return "type date"
    if column in INTEGER_COLUMNS or column in CALENDAR_INTEGERS:
        return "Int64.Type"
    if column == "occupancy_percentage":
        return "type number"
    return "type text"


def column_definition(table, column, definitions):
    kind = m_type(column)
    data_type = {"type date": "dateTime", "Int64.Type": "int64", "type number": "double", "type text": "string"}[kind]
    result = {"name": column, "dataType": data_type, "sourceColumn": column,
              "summarizeBy": "none", "lineageTag": lineage(f"{table}.{column}")}
    if table == "Bookings":
        if column in HIDDEN_COLUMNS:
            result["isHidden"] = True
        if column == "booking_id":
            result.update(isKey=True, isUnique=True, isNullable=False)
        if column.startswith("flag_"):
            result["displayFolder"] = "Source quality flags"
            result["description"] = "1 indicates a flagged source-record condition; 0 indicates no flag. Flagged chronology stays in booking totals."
        elif column in {"occupancy_percentage", "on_time_delay_mins"}:
            result["displayFolder"] = "Reported operational fields"
            result["description"] = definitions["avg_record_occupancy_pct" if column == "occupancy_percentage" else "avg_record_delay_mins"]
        elif column in {"lead_time_days", "valid_lead_time_days"}:
            result["displayFolder"] = "Lead time"
            result["description"] = definitions["lead_time"]
        elif column.endswith("_inr"):
            result["displayFolder"] = "Recorded amounts"
            result["description"] = definitions["booking_value_inr"] if column == "booking_value_inr" else "Supplied INR charge component at booking grain; not a recognized revenue or profit measure."
        elif column == "train_number":
            result["description"] = definitions["distinct_train_numbers"]
    if data_type == "dateTime":
        result["formatString"] = "dd mmm yyyy"
        result["annotations"] = [{"name": "UnderlyingDateTimeDataType", "value": "Date"}]
    elif data_type == "int64":
        result["formatString"] = "#,##0"
    elif column == "occupancy_percentage":
        result["formatString"] = '0.0"%"'
    if table == "DimDate":
        if column == "date":
            result.update(isKey=True, isUnique=True, isNullable=False)
        if column == "month_name":
            result["sortByColumn"] = "month_number"
        if column == "weekday":
            result["sortByColumn"] = "weekday_number"
    return result


def calendar_csv(booking_rows):
    dates = [date.fromisoformat(row[field]) for row in booking_rows for field in ("booking_date", "travel_date")]
    start, end = date(min(dates).year, 1, 1), date(max(dates).year, 12, 31)
    columns = ["date", "year", "quarter", "month_number", "month_name", "year_month", "weekday", "weekday_number", "is_weekend"]
    rows = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        rows.append([day.isoformat(), day.year, (day.month - 1) // 3 + 1, day.month,
                     day.strftime("%B"), day.strftime("%Y-%m"), day.strftime("%A"), day.weekday() + 1,
                     int(day.weekday() >= 5)])
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return text.getvalue().encode("utf-8"), columns


def measure_definitions(metrics):
    source = (ROOT / "powerbi/Measures.dax").read_text(encoding="utf-8")
    source = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))
    matches = list(re.finditer(r"^([A-Za-z][A-Za-z0-9 ]*)\s*=", source, flags=re.M))
    definitions = [(match.group(1).strip(), source[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(source)].strip())
                   for i, match in enumerate(matches)]
    descriptions = {
        "Bookings": metrics["definitions"]["bookings"],
        "Recorded Booking Value": metrics["definitions"]["booking_value_inr"],
        "Passengers": metrics["definitions"]["passengers"],
        "Distinct Users": metrics["definitions"]["total_users"],
        "Distinct Train Numbers": metrics["definitions"]["distinct_train_numbers"],
        "Mean Reported Occupancy Pct": metrics["definitions"]["avg_record_occupancy_pct"],
        "Mean Record Delay Mins": metrics["definitions"]["avg_record_delay_mins"],
        "Cancellation Rate": metrics["definitions"]["cancellation_rate_pct"],
        "Valid Lead Time Records": "Count of nonblank, nonnegative lead times within the selected accepted booking cohort.",
        "Mean Valid Lead Time Days": metrics["definitions"]["lead_time"],
        "Invalid Chronology Rate": "Fraction of selected booking records whose Booking_Date is after Travel_Date.",
        "Selected Route Value Share": "Recorded value divided by value for selected routes, preserving all other filters.",
        "Bookings MoM Pct": "Month-over-month booking-count change in DimDate context. Blank when the preceding month has no bookings.",
    }
    # These full-source snapshot measures deliberately ignore report filters.
    quality_fields = {
        "Raw Source Records": "source_row_count",
        "Exact Duplicates Removed": "exact_duplicate_rows_removed",
        "Quarantined Records": "quarantined_rows",
        "Conflicting Booking IDs": "conflicting_booking_id_groups",
        "Accepted Source Records": "accepted_row_count",
        "Raw Source Booking Value": "source_booking_value_inr",
        "Duplicate Booking Value": "exact_duplicate_value_removed_inr",
        "Quarantined Booking Value": "quarantined_booking_value_inr",
        "Accepted Source Booking Value": "accepted_booking_value_inr",
    }
    for name, key in quality_fields.items():
        definitions.append((name, str(metrics["quality"][key])))
        descriptions[name] = "Fixed full-source reconciliation control for the embedded snapshot; intentionally unaffected by report filters."
    dynamic_extras = {
        "Train Metadata Conflict Records": "COALESCE ( SUM ( 'Bookings'[flag_train_metadata_conflict] ), 0 )",
        "Occupancy Conflict Records": "COALESCE ( SUM ( 'Bookings'[flag_train_date_occupancy_conflict] ), 0 )",
        "Delay Conflict Records": "COALESCE ( SUM ( 'Bookings'[flag_train_date_delay_conflict] ), 0 )",
        "Charge Mismatch Records": "COALESCE ( SUM ( 'Bookings'[flag_charge_mismatch] ), 0 )",
        "Booking Value Per Passenger": "DIVIDE ( [Recorded Booking Value], [Passengers] )",
        "Average Passengers Per Booking": "DIVIDE ( [Passengers], [Bookings] )",
        "Users With Multiple Selected Bookings": "COALESCE ( COUNTROWS ( FILTER ( VALUES ( 'Bookings'[user_id] ), CALCULATE ( COUNTROWS ( 'Bookings' ) ) > 1 ) ), 0 )",
        "Base Fare Value": "COALESCE ( SUM ( 'Bookings'[base_fare_inr] ), 0 )",
        "Tatkal Charge Value": "COALESCE ( SUM ( 'Bookings'[surge_tatkal_charges_inr] ), 0 )",
        "Catering Charge Value": "COALESCE ( SUM ( 'Bookings'[catering_charges_inr] ), 0 )",
        "Taxes and Convenience Value": "COALESCE ( SUM ( 'Bookings'[taxes_and_convenience_inr] ), 0 )",
    }
    definitions.extend(dynamic_extras.items())
    measures = []
    for name, expression in definitions:
        is_pct = name.endswith(" Pct") or name.endswith(" Rate") or name.endswith(" Share")
        is_value = "Value" in name and not is_pct
        is_decimal = name in {"Mean Record Delay Mins", "Mean Valid Lead Time Days", "Average Passengers Per Booking"}
        fmt = "0.0%" if is_pct else '"₹" #,##0.00;("₹" #,##0.00);"₹" 0.00' if is_value else "0.0" if is_decimal else "#,##0"
        folder = "04 Full-source reconciliation" if name in quality_fields else "03 Data quality" if any(token in name for token in ("Chronology", "Conflict", "Mismatch", "Lead Time")) else "02 Booking mix" if name in dynamic_extras else "01 Core KPIs"
        measures.append({"name": name, "expression": expression, "formatString": fmt,
                         "displayFolder": folder, "description": descriptions.get(name, "Calculated over the current selected accepted-booking population unless explicitly stated otherwise."),
                         "lineageTag": lineage("measure." + name)})
    return measures


def build():
    metrics = json.loads((ROOT / "reports/metrics.json").read_text(encoding="utf-8"))
    clean_bytes = (ROOT / "data/processed/bookings_clean.csv").read_bytes()
    booking_rows = list(csv.DictReader(io.StringIO(clean_bytes.decode("utf-8"))))
    booking_columns = list(booking_rows[0])
    date_bytes, date_columns = calendar_csv(booking_rows)
    tables = []
    for name, csv_bytes, columns in [("Bookings", clean_bytes, booking_columns), ("DimDate", date_bytes, date_columns)]:
        table = {
            "name": name, "lineageTag": lineage("table." + name),
            "description": metrics["definitions"]["population"] if name == "Bookings" else "Continuous full-year calendar spanning all supplied booking and travel dates. Booking date is the active relationship.",
            "columns": [column_definition(name, column, metrics["definitions"]) for column in columns],
            "partitions": [embedded_partition(name, csv_bytes, columns, {column: m_type(column) for column in columns})],
            "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
        }
        if name == "Bookings":
            table["measures"] = measure_definitions(metrics)
        else:
            table["dataCategory"] = "Time"
            table["hierarchies"] = [{"name": "Calendar", "lineageTag": lineage("DimDate.Calendar"),
                                      "levels": [{"name": "Year", "ordinal": 0, "column": "year"},
                                                 {"name": "Month", "ordinal": 1, "column": "year_month"},
                                                 {"name": "Date", "ordinal": 2, "column": "date"}]}]
        tables.append(table)
    model = {
        "name": "IRCTC Business Insights", "compatibilityLevel": 1600,
        "model": {
            "culture": "en-US", "sourceQueryCulture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3", "discourageImplicitMeasures": True,
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": False},
            "tables": tables,
            "relationships": [{
                "name": lineage("relationship." + source_column), "fromTable": "Bookings",
                "fromColumn": source_column, "fromCardinality": "many", "toTable": "DimDate",
                "toColumn": "date", "toCardinality": "one", "isActive": source_column == "booking_date",
                "crossFilteringBehavior": "oneDirection", "securityFilteringBehavior": "oneDirection",
                "joinOnDateBehavior": "dateAndTime",
            } for source_column in ("booking_date", "travel_date")],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": '["Bookings","DimDate"]'},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                {"name": "IRCTC_OriginalSourceSha256", "value": metrics["source_sha256"]},
                {"name": "IRCTC_Scope", "value": "Synthetic educational sample; recorded booking value includes all statuses; not official IRCTC operational or financial reporting."},
            ],
        },
    }
    descriptor = {"$schema": PBISM_SCHEMA, "version": "1.0", "settings": {"qnaEnabled": False}}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    (MODEL_DIR / "definition.pbism").write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
    (MODEL_DIR / "model.bim").write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Round-trip emitted artifacts, not merely the pre-serialization structures.
    saved = json.loads((MODEL_DIR / "model.bim").read_text(encoding="utf-8"))
    saved_tables = {table["name"]: table for table in saved["model"]["tables"]}
    decoded_bookings = decode_partition(saved_tables["Bookings"]["partitions"][0])
    decoded_dates = decode_partition(saved_tables["DimDate"]["partitions"][0])
    assert decoded_bookings == clean_bytes
    assert decoded_dates == date_bytes
    loaded_rows = list(csv.DictReader(io.StringIO(decoded_bookings.decode("utf-8"))))
    loaded_dates = list(csv.DictReader(io.StringIO(decoded_dates.decode("utf-8"))))
    date_keys = {row["date"] for row in loaded_dates}
    assert len(loaded_rows) == metrics["totals"]["row_count"]
    assert sum(int(row["booking_value_inr"]) for row in loaded_rows) == metrics["totals"]["booking_value_inr"]
    assert len(date_keys) == len(loaded_dates)
    assert all(row[field] in date_keys for row in loaded_rows for field in ("booking_date", "travel_date"))
    assert sum(relation["isActive"] for relation in saved["model"]["relationships"]) == 1
    model_columns = {name: {column["name"] for column in table["columns"]} for name, table in saved_tables.items()}
    measures = saved_tables["Bookings"]["measures"]
    assert len({measure["name"] for measure in measures}) == len(measures)
    measure_names = {measure["name"] for measure in measures}
    dependencies = {}
    for measure in measures:
        for table, column in re.findall(r"'([^']+)'\[([^\]]+)\]", measure["expression"]):
            assert column in model_columns[table], (measure["name"], table, column)
        without_columns = re.sub(r"'[^']+'\[[^\]]+\]", "", measure["expression"])
        dependencies[measure["name"]] = set(re.findall(r"\[([^\]]+)\]", without_columns))
        assert dependencies[measure["name"]] <= measure_names, measure["name"]
    def visit_measure(name, ancestors):
        assert name not in ancestors, ("Circular measure reference", name)
        for dependency in dependencies[name]:
            visit_measure(dependency, ancestors | {name})
    for name in dependencies:
        visit_measure(name, set())
    for table_name, table_rows in [("Bookings", loaded_rows), ("DimDate", loaded_dates)]:
        for column in saved_tables[table_name]["columns"]:
            values = [row[column["name"]] for row in table_rows]
            for value in values:
                if value == "":
                    assert column["name"] == "valid_lead_time_days"
                elif column["dataType"] == "int64":
                    assert -(2 ** 63) <= int(value) < 2 ** 63
                elif column["dataType"] == "double":
                    float(value)
                elif column["dataType"] == "dateTime":
                    date.fromisoformat(value)
            if column.get("isKey"):
                assert "" not in values and len(values) == len(set(values))
            if column.get("sortByColumn"):
                mapping = {}
                for row in table_rows:
                    assert mapping.setdefault(row[column["name"]], row[column["sortByColumn"]]) == row[column["sortByColumn"]]
    date_ordinals = sorted(date.fromisoformat(key).toordinal() for key in date_keys)
    assert date_ordinals == list(range(date_ordinals[0], date_ordinals[-1] + 1))
    checks = {
        "booking_payload_matches_clean_csv_bytes": True,
        "calendar_payload_round_trip": True,
        "embedded_booking_count_and_value_match_controls": True,
        "column_types_parse_for_every_embedded_cell": True,
        "keys_are_unique_and_nonblank": True,
        "date_relationships_have_no_orphans": True,
        "exactly_one_active_date_relationship": True,
        "full_calendar_is_contiguous": True,
        "sort_columns_have_valid_functional_dependencies": True,
        "all_DAX_column_and_measure_references_exist": True,
        "DAX_measure_dependency_graph_is_acyclic": True,
    }
    for table in saved_tables.values():
        expression = "\n".join(table["partitions"][0]["source"]["expression"])
        executable_lines = "\n".join(line for line in expression.splitlines() if not line.strip().startswith("//"))
        assert not re.search(r"\b(?:File\.Contents|Web\.Contents|Sql\.Database|Folder\.Files)\s*\(", executable_lines)
    checks["no_external_file_network_or_database_calls"] = True
    verification = {
        "status": "PASS", "scope": "Static semantic model and embedded-data checks; not native DAX or M engine execution.",
        "checks": checks, "booking_row_count": len(loaded_rows), "calendar_row_count": len(loaded_dates),
        "measure_count": len(measures), "booking_columns": len(booking_columns),
        "booking_value_inr": sum(int(row["booking_value_inr"]) for row in loaded_rows),
        "source_csv_sha256": hashlib.sha256(clean_bytes).hexdigest(),
        "native_engine_execution": "Not available on this macOS host. Refresh and inspect in Power BI Desktop on Windows.",
        "sources": SOURCES,
    }
    (MODEL_DIR / "MODEL_VERIFICATION.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    notes = f'''# Native semantic model

This folder contains a Power BI semantic model definition in the supported TMSL `model.bim` format. `definition.pbism` version 1.0 selects that format. The parent report refers to this folder by a relative path.

The `Bookings` table contains **{len(loaded_rows):,} accepted records**, all **{len(booking_columns)}** cleaned columns and **{len(measures)} explicit measures**. `DimDate` contains **{len(loaded_dates)}** continuous calendar dates. The booking-date relationship is active and the travel-date relationship is inactive. The calendar has a Year / Month / Date hierarchy and month/day sorting.

Both tables use embedded, compressed CSV snapshots. The queries have no local file path, web request, credentials or gateway dependency. On first open in Power BI Desktop for Windows, select **Refresh** to materialize the embedded tables, check the figures, and use **Save As** if a `.pbix` file is needed. No `cache.abf` data cache is included.

Baseline recorded booking value is **INR {metrics['totals']['booking_value_inr']:,}**. All statuses are retained. Full-source reconciliation measures are fixed snapshot controls; booking and quality measures otherwise follow report filter context. Occupancy and delay describe booking-record fields and do not establish service performance. This is a synthetic educational dataset.

The builder passed **{len(checks)} static and embedded-data checks**, recorded in `MODEL_VERIFICATION.json`. Payload decompression recovers the accepted CSV byte-for-byte; types, keys, relationships, date continuity, sorting and DAX references were checked. These checks do not compile DAX, execute Power Query M or confirm Power BI rendering. Native execution remains a Windows Desktop verification step.

To rebuild after updating the pipeline outputs, run `python3 src/build_powerbi_model.py` from the main project folder, then refresh the project in Desktop. The builder has no third-party Python dependency. Close Desktop before replacing its model files.

Official references: [Power BI semantic model folder](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset), [TMSL table objects](https://learn.microsoft.com/en-us/analysis-services/tmsl/tables-object-tmsl), [relationships](https://learn.microsoft.com/en-us/analysis-services/tmsl/relationships-object-tmsl), and [Power Query decompression](https://learn.microsoft.com/en-us/powerquery-m/binary-decompress).
'''
    (MODEL_DIR / "MODEL_NOTES.md").write_text(notes, encoding="utf-8")
    print(json.dumps({"model": "powerbi/IRCTC.SemanticModel/model.bim", "tables": list(saved_tables),
                      "booking_columns": len(booking_columns), "measures": len(measures),
                      "embedded_booking_rows": len(loaded_rows), "calendar_rows": len(loaded_dates),
                      "embedded_booking_value_inr": sum(int(row["booking_value_inr"]) for row in loaded_rows),
                      "csv_round_trip": "exact byte match", "native_engine_execution": "not available"}, indent=2))


if __name__ == "__main__":
    build()

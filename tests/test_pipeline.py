"""Meaningful identity, financial, grain and artifact-contract tests (stdlib)."""
import csv
import hashlib
import importlib.util
import json
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pipeline", ROOT / "src/pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example = pipeline.read_source(ROOT / "data/raw/bookings.csv")[0]

    def sample(self, line=2, **changes):
        return {**self.example, "source_row_number": line, **changes}

    def test_full_duplicate_ignores_source_line_number(self):
        accepted, duplicates, quarantine, fields = pipeline.partition_rows([self.sample(), self.sample(line=3)])
        self.assertEqual((len(accepted), len(duplicates), len(quarantine)), (1, 1, 0))
        self.assertEqual(duplicates[0]["retained_source_row_number"], 2)
        self.assertEqual(fields, {})

    def test_conflicting_id_quarantines_every_member(self):
        accepted, duplicates, quarantine, fields = pipeline.partition_rows([
            self.sample(), self.sample(line=3, Booking_Date="2025-01-01")])
        self.assertEqual(accepted, [])
        self.assertEqual(len(quarantine), 2)
        self.assertEqual(fields, {"Booking_Date": 1})

    def test_exact_duplicates_removed_before_conflicts(self):
        accepted, duplicates, quarantine, _ = pipeline.partition_rows([
            self.sample(), self.sample(line=3), self.sample(line=4, Booking_Date="2025-01-01")])
        self.assertEqual((len(accepted), len(duplicates), len(quarantine)), (0, 1, 2))

    def test_distinct_ids_with_same_values_are_retained(self):
        accepted, _, quarantine, _ = pipeline.partition_rows([
            self.sample(), self.sample(line=3, Booking_ID="NEW_ID")])
        self.assertEqual(len(accepted), 2)
        self.assertEqual(quarantine, [])

    def test_negative_lead_is_flagged_and_excluded_only_from_lead_mean(self):
        bad = pipeline.typed_row(self.sample(Booking_Date="2025-06-21", Travel_Date="2025-06-20"))
        good = pipeline.typed_row(self.sample(line=3, Booking_ID="GOOD", Booking_Date="2025-06-18", Travel_Date="2025-06-20"))
        self.assertEqual(bad["lead_time_days"], -1)
        self.assertIsNone(bad["valid_lead_time_days"])
        totals = pipeline.summarize([bad, good])
        self.assertEqual(totals["row_count"], 2)
        self.assertEqual(totals["booking_value_inr"], 2 * good["booking_value_inr"])
        self.assertEqual(totals["valid_lead_time_count"], 1)
        self.assertEqual(totals["avg_valid_lead_time_days"], 2)

    def test_zero_day_lead_is_valid(self):
        row = pipeline.typed_row(self.sample(Booking_Date="2025-06-20", Travel_Date="2025-06-20"))
        self.assertEqual(row["valid_lead_time_days"], 0)
        self.assertEqual(row["flag_invalid_chronology"], 0)

    def test_charge_mismatch_is_detected(self):
        row = pipeline.typed_row(self.sample(Total_Revenue_INR="999"))
        self.assertEqual(row["flag_charge_mismatch"], 1)
        self.assertEqual(row["charge_difference_inr"], 999 - row["charge_components_inr"])

    def test_invalid_ranges_and_formats_rejected(self):
        for changes in [{"Occupancy_Percentage": "101"}, {"Occupancy_Percentage": "nan"},
                        {"Passenger_Count": "0"}, {"Base_Fare_INR": "-1"},
                        {"Passenger_Count": "1.5"}, {"Booking_Date": "2025-02-30"},
                        {"Booking_Time": "24:15:00"}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pipeline.typed_row(self.sample(**changes))

    def test_train_date_conflicts_use_group_flags(self):
        a = pipeline.typed_row(self.sample())
        b = pipeline.typed_row(self.sample(line=3, Booking_ID="B", Occupancy_Percentage="90.0",
                                          On_Time_Delay_Mins="45", Train_Name="Other label"))
        profile = pipeline.profile_train_fields([a, b])
        self.assertEqual(profile["train_date_occupancy_conflicting_groups"], 1)
        self.assertEqual(profile["train_date_delay_conflicting_groups"], 1)
        self.assertEqual(a["flag_train_date_occupancy_conflict"], 1)
        self.assertEqual(b["flag_train_metadata_conflict"], 1)

    def test_ambiguous_train_dimension_is_rejected(self):
        a = pipeline.typed_row(self.sample())
        b = pipeline.typed_row(self.sample(line=3, Booking_ID="B", Train_Capacity="777"))
        with self.assertRaises(ValueError):
            pipeline.build_dimensions([a, b])

    def test_empty_summary_does_not_invent_zero_average(self):
        summary = pipeline.summarize([])
        self.assertEqual(summary["row_count"], 0)
        self.assertIsNone(summary["avg_booking_value_inr"])
        self.assertIsNone(summary["avg_record_occupancy_pct"])


class DeliveredArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = json.loads((ROOT / "reports/metrics.json").read_text())
        cls.validation = json.loads((ROOT / "reports/validation.json").read_text())
        cls.dashboard = json.loads((ROOT / "reports/dashboard_data.json").read_text())
        cls.rows = read_csv(ROOT / "data/processed/bookings_clean.csv")
        cls.connection = sqlite3.connect(f"file:{ROOT / 'data/irctc.sqlite'}?mode=ro", uri=True)

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def test_known_dataset_control_totals(self):
        # Regression controls independently recomputed from the supplied original CSV.
        expected = {"row_count": 19301, "booking_value_inr": 51279303, "passengers": 38528,
                    "total_users": 19101, "distinct_train_numbers": 540,
                    "invalid_chronology_count": 11408, "valid_lead_time_count": 7893}
        for key, value in expected.items():
            self.assertEqual(self.metrics["totals"][key], value, key)

    def test_source_hash_and_validation_pass(self):
        digest = hashlib.sha256((ROOT / "data/raw/bookings.csv").read_bytes()).hexdigest()
        self.assertEqual(digest, self.metrics["source_sha256"])
        self.assertEqual(self.validation["status"], "PASS")
        self.assertTrue(all(self.validation["checks"].values()))

    def test_row_and_value_reconciliation_independent_csv_read(self):
        source = read_csv(ROOT / "data/raw/bookings.csv")
        removed = read_csv(ROOT / "data/processed/exact_duplicates_removed.csv")
        quarantine = read_csv(ROOT / "data/processed/booking_id_conflicts_quarantine.csv")
        self.assertEqual(len(source), len(self.rows) + len(removed) + len(quarantine))
        source_total = sum(int(row["Total_Revenue_INR"]) for row in source)
        excluded_total = sum(int(row["Total_Revenue_INR"]) for row in removed + quarantine)
        self.assertEqual(source_total, excluded_total + sum(int(row["booking_value_inr"]) for row in self.rows))
        ids = [row["booking_id"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(set(ids) & {row["Booking_ID"] for row in quarantine})

    def test_sqlite_relations_and_integrity(self):
        self.assertEqual(self.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        joined = self.connection.execute('''SELECT COUNT(*), SUM(f.booking_value_inr) FROM fact_booking f
            JOIN dim_train t ON t.train_number=f.train_number
            JOIN dim_route r ON r.route_key=f.route_key
            JOIN dim_date d ON d.date=f.booking_date''').fetchone()
        self.assertEqual(joined, (19301, 51279303))

    def test_sql_and_csv_numeric_parity(self):
        sql = self.connection.execute('''SELECT COUNT(*), SUM(booking_value_inr), SUM(passenger_count),
            COUNT(DISTINCT user_id), AVG(occupancy_percentage), SUM(flag_invalid_chronology)
            FROM fact_booking''').fetchone()
        totals = self.metrics["totals"]
        self.assertEqual(sql[:4], (totals["row_count"], totals["booking_value_inr"], totals["passengers"], totals["total_users"]))
        self.assertAlmostEqual(sql[4], totals["avg_record_occupancy_pct"], places=5)
        self.assertEqual(sql[5], totals["invalid_chronology_count"])

    def test_dashboard_record_grain_and_anonymous_user_equality(self):
        columns = self.dashboard["columns"]
        rows = [dict(zip(columns, values)) for values in self.dashboard["rows"]]
        self.assertEqual(len(rows), 19301)
        self.assertEqual(sum(row["booking_value_inr"] for row in rows), 51279303)
        self.assertEqual(len({row["user_key"] for row in rows}), 19101)
        self.assertNotIn("user_id", columns)
        user_pairs = {}
        for clean, dashboard in zip(self.rows, rows):
            self.assertEqual(clean["booking_id"], dashboard["booking_id"])
            self.assertEqual(user_pairs.setdefault(clean["user_id"], dashboard["user_key"]), dashboard["user_key"])
        for row in rows:
            self.assertIn(row["flag_charge_mismatch"], (0, 1))

    def test_filtered_dashboard_totals_match_sql(self):
        columns = self.dashboard["columns"]
        rows = [dict(zip(columns, values)) for values in self.dashboard["rows"]]
        selected = [row for row in rows if row["booking_channel"] == "IRCTC App"
                    and row["booking_status"] == "Confirmed" and "2025-03" <= row["booking_month"] <= "2025-08"]
        sql = self.connection.execute('''SELECT COUNT(*), SUM(booking_value_inr), SUM(passenger_count),
            COUNT(DISTINCT user_id) FROM fact_booking WHERE booking_channel='IRCTC App'
            AND booking_status='Confirmed' AND booking_month BETWEEN '2025-03' AND '2025-08' ''').fetchone()
        self.assertEqual(sql, (len(selected), sum(row["booking_value_inr"] for row in selected),
                               sum(row["passenger_count"] for row in selected), len({row["user_key"] for row in selected})))

    def test_no_false_train_name_functional_dependency(self):
        names = self.connection.execute("PRAGMA table_info(dim_train)").fetchall()
        self.assertNotIn("train_name", [column[1] for column in names])
        conflict_count = self.connection.execute('''SELECT COUNT(*) FROM
            (SELECT train_number FROM fact_booking GROUP BY train_number HAVING COUNT(DISTINCT train_name)>1)''').fetchone()[0]
        self.assertEqual(conflict_count, 540)

    def test_sql_question_file_executes_read_only(self):
        buffer = ""
        query_count = 0
        for line in (ROOT / "sql/analysis_queries.sql").read_text().splitlines(True):
            buffer += line
            if sqlite3.complete_statement(buffer):
                self.connection.execute(buffer).fetchall()
                query_count += 1
                buffer = ""
        self.assertGreaterEqual(query_count, 12)


if __name__ == "__main__":
    unittest.main()

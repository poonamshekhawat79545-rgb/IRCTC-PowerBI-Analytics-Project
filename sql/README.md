# SQL analysis

`data/irctc.sqlite` is a ready-to-query SQLite database. `src/pipeline.py` rebuilds it from the immutable source CSV using Python's standard library. Run commands from the project folder.

```sh
python3 src/pipeline.py
python3 -m unittest discover -s tests -v
```

Open `analysis_queries.sql` in a SQLite client and run its 18 numbered questions against the database. If the optional SQLite command-line program is installed:

```sh
sqlite3 -header -column data/irctc.sqlite < sql/analysis_queries.sql
```

You can also use Python without installing a database client:

```python
import sqlite3
connection = sqlite3.connect("file:data/irctc.sqlite?mode=ro", uri=True)
for row in connection.execute("SELECT * FROM v_monthly ORDER BY booking_month"):
    print(row)
connection.close()
```

The four tables are `fact_booking`, `dim_date`, `dim_route`, and `dim_train`. `schema.sql` is the generated, reviewable DDL; the pipeline handles imports and foreign keys. Convenience views expose monthly, route, channel, and status totals. The fact grain is one accepted booking ID. Booking and travel dates reference the same date table in SQLite; a BI model should activate the booking-date relationship and keep travel date inactive or use a role-playing calendar.

`dim_train` contains number, type and capacity only. All 540 numbers have multiple names and routes in the supplied file. Assigning a single name or route to each number would invent a relationship. Route details are consistent at the supplied route-label grain and live in `dim_route`.

All amounts are recorded booking values, including cancelled and waitlisted records. Refund, settlement and revenue-recognition facts are absent. Passenger totals are recorded passenger counts, not observed journeys. The supplied occupancy/delay fields are summarized per booking and do not establish actual service performance. Negative booking lead times remain flagged in facts and are excluded only from valid lead-time averages.

Baseline controls: **19,301** accepted bookings; **₹51,279,303** recorded booking value; **38,528** recorded passengers; **19,101** distinct supplied user IDs. `reports/validation.json` records count/value reconciliation to the source, rejected identities, dimensional integrity, and aggregate consistency.

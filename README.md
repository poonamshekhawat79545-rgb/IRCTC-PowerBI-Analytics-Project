# IRCTC Business Insights

A Power BI data analyst portfolio project built from the supplied synthetic booking dataset. It connects source profiling and exception handling to a native report and semantic model, Python, SQL analysis, an offline dashboard, an Excel workbook and a written business case.

**Start with the [Power BI opening guide](powerbi/START_HERE.md).** On Windows, open [`powerbi/IRCTC.pbip`](powerbi/IRCTC.pbip), select **Refresh**, verify the figures and use **Save as → Power BI file (.pbix)**. The report's three pages and semantic model are already authored, with the accepted source snapshot embedded.

For an additional offline presentation, open [`dashboard/IRCTC_Dashboard.html`](dashboard/IRCTC_Dashboard.html) in your browser. It is self-contained and needs no installation.

## What is included

| Deliverable | Where to start | What it demonstrates |
|---|---|---|
| Native Power BI project | `powerbi/IRCTC.pbip`, `powerbi/START_HERE.md` | Three report pages, 60 native visuals, 38 measures, page slicers, cross-filtering and an embedded semantic model |
| Interactive dashboard | `dashboard/IRCTC_Dashboard.html` | Five filters, three analytical pages, live KPIs, trend and mix charts, CSV export |
| Excel analysis | `reports/IRCTC_Analysis.xlsx` | Formula-driven summaries, native charts, analytical source data and quality checks |
| Executive report | `reports/Executive_Report.pdf` | Business questions, quantified observations, recommended investigations and limitations |
| Executed notebook | `notebooks/IRCTC_Analysis.ipynb` | Python profiling, amount reconciliation, SQL analysis and independent controls |
| Python pipeline | `src/pipeline.py` | Deterministic cleaning, flags, dimensions, exports and validation |
| SQL database and queries | `data/irctc.sqlite`, `sql/` | Relational analysis and reusable business queries |
| Power BI implementation notes | `powerbi/POWER_BI_GUIDE.md` | Model and report structure, theme, reproducible builders and Windows acceptance checks |
| Portfolio materials | `docs/CASE_STUDY.md`, `docs/INTERVIEW_GUIDE.md` | Case study, project walkthrough, interview preparation and resume bullets |
| Data documentation | `docs/DATA_DICTIONARY.md`, `docs/SOURCES.md` | Grain, field definitions, lineage and reference attribution |

The native `.pbip` project has passed official JSON-schema, field-reference, geometry and embedded-data checks. Power BI Desktop is unavailable on this Mac, so native opening, M/DAX execution, visual rendering and `.pbix` saving remain to be verified on Windows. See the [concrete acceptance checklist](powerbi/POWER_BI_ACCEPTANCE_CHECKLIST.md); no `.pbix` is claimed or included.

## The business problem

Describe the sample's booking demand and recorded value by month, route, booking type and channel. Explain status and customer activity. Identify which questions the data cannot answer reliably before presenting recommendations.

The strongest analytical decision in this project is the cleaning policy: a plausible-looking chart should not conceal conflicting identifiers or impossible chronology.

## Baseline controls

| Measure | Result |
|---|---:|
| Raw source records | 20,000 |
| Exact duplicate removed | 1 |
| Conflicting-ID records quarantined | 698 across 349 IDs |
| Accepted bookings | 19,301 |
| Recorded booking value | INR 51,279,303 (INR 5.13 crore) |
| Passengers on booking records | 38,528 |
| Distinct users | 19,101 |
| Distinct train numbers | 540 |
| Accepted records booked after travel | 11,408 (59.1%) |
| Records eligible for lead-time analysis | 7,893 |

Amount reconciliation: **53,055,565 − 660 − 1,775,602 = 51,279,303 INR**.

## Method and metric rules

1. Preserve the original CSV values in `data/raw/bookings.csv`.
2. Remove only exact duplicate excess. Set aside **every** row belonging to a remaining conflicting booking ID. Do not select an arbitrary survivor.
3. Keep impossible chronology as an explicit flag. Include it in descriptive booking-date totals, but exclude it from advance-booking measures.
4. Reconcile recorded total value to the four supplied charge components. Preserve all selected statuses.
5. Model dimensions only at a grain supported by the source. Train number has inconsistent names and routes, so those attributes cannot be forced into a one-row-per-number lookup.
6. Reconcile accepted CSV totals with SQLite, the dashboard and the workbook. Keep traceable exception exports.

`booking_value_inr` is a renamed source amount, **not recognized revenue, profit or collected cash**. Passengers are people on booking records, not proven journeys. Distinct train numbers do not establish trains operated. Occupancy and delay are descriptions of supplied booking-record fields because those fields conflict within train-date groups. This is a synthetic portfolio exercise, not an official IRCTC report.

## Reproduce the core analysis

Use Python 3.10 or later. The pipeline, SQL and offline dashboard build use the standard library and need no third-party packages.

From this project directory:

```sh
python3 src/pipeline.py
python3 -m unittest discover -s tests -v
python3 src/build_dashboard.py
```

The pipeline recreates its processed CSVs, SQLite model and machine-readable reports from `data/raw/bookings.csv`. The dashboard build embeds the resulting row-level JSON into the HTML. To analyze a new dataset, retain the source schema, replace the CSV, run the checks and review every exception. The delivered regression tests deliberately contain this original dataset's controls; independently reconcile replacement data before updating those expectations. Do not assume the original totals apply to a replacement dataset.

Open the notebook from the project or `notebooks/` directory and run all cells. It uses only standard Python libraries, although your notebook application itself must support a Python kernel. Its saved outputs were executed during project creation.

The Excel workbook and PDF are delivered analytical snapshots with editable formulas/content where applicable. They are not regenerated by the three commands above. After replacing the source, refresh or rebuild these presentation files and reconcile them to the new controls before sharing them. See workbook notes for its formula boundaries.

To rebuild the Power BI snapshot after processing an intentional source update, close Desktop and run `python3 src/build_powerbi_model.py`. Ordinary Desktop Refresh loads the embedded snapshot; it does not reread the external CSV. `python3 src/build_powerbi_report.py` regenerates and overwrites the authored report pages; preserve any manual report edits first. Review static report text and control expectations when replacing the dataset. Both builders use only standard Python libraries. Optional structural validation uses `python3 -m pip install jsonschema`, then `python3 src/validate_powerbi_project.py` (internet access downloads Microsoft's schemas on the first run).

## Review and present

Open the report for the concise business story, then use the dashboard to demonstrate an intersecting filter selection. Show the data-quality reconciliation and the exception files. Walk through one SQL query and its Python cross-check. Use the interview guide to explain why the metric names differ from the supplied visual template.

See `reports/QA_SUMMARY.md` for validation performed and remaining native-application limits.

To repeat the additional dashboard logic checks, use Node.js 20 or later (no packages needed):

```sh
python3 tests/dashboard_scenarios.py
node tests/test_dashboard_logic.mjs
```

These execute the actual dashboard calculation code against independent CSV cohorts in an in-memory document model. They do not establish visual browser layout or native event behavior; local HTML browser preview was blocked by this environment's URL policy.

## Sources and attribution

The dataset, theme guide and background image were supplied by the user. The source CSV filename explicitly describes the data as synthetic. The two linked DataCliq videos informed the project structure and visual direction. The six-color theme is retained, while metric definitions are based on independent analysis. Original design references are preserved in `references/`.

No claim of affiliation with IRCTC, Indian Railways or DataCliq is made. No public redistribution license for the supplied dataset or design assets was included; confirm their terms before publishing those source assets. The package has been created locally and has not been published to a public repository or website.

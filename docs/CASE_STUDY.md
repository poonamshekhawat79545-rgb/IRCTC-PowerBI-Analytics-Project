# IRCTC Business Insights: an end-to-end data analyst case study

## Business question

How are bookings and recorded booking value distributed across time, routes and channels, and which data-quality issues prevent stronger commercial or operational conclusions?

This is an independent educational portfolio project inspired by DataCliq's linked tutorials. No official IRCTC affiliation or production-data provenance is established. The decision maker is a hypothetical commercial analytics manager; no real stakeholder adoption or financial improvement is claimed.

## Approach

1. Preserve and profile the supplied CSV, recording its checksum and schema.
2. Define one booking ID per analytical row; distinguish identical repeats from conflicting records.
3. Reconcile every exclusion by both row count and recorded value. Retain exceptions in auditable files.
4. Model accepted bookings in SQLite, with valid date, route and train dimensions. Restrict train attributes to those that are consistent.
5. Create common metric definitions and descriptive summaries, then present them through the dashboard, workbook, SQL, notebook and report.
6. Validate arithmetic, unique IDs, dimensional integrity and aggregate reconciliation. Make limitations visible alongside results.

## Reconciliation

| Stage | Rows | Recorded value (INR) |
|---|---:|---:|
| Supplied source | 20,000 | 53,055,565 |
| Less one exact duplicate occurrence | (1) | (660) |
| Less all members of conflicting-ID groups | (698) | (1,775,602) |
| Accepted booking cohort | **19,301** | **51,279,303** |

349 booking IDs each had multiple distinct records after identical deduplication; the differences were booking dates. Keeping an arbitrary version would invent a resolution. All 698 records were isolated instead. The accepted cohort retains 96.505% of source rows.

## Results

| Measure | Accepted-cohort result | Interpretation |
|---|---:|---|
| Booking IDs | 19,301 | One accepted ID per row |
| Recorded booking value | INR 51,279,303 | All statuses; not realized revenue |
| Recorded passengers | 38,528 | Not observed passengers carried |
| Supplied user IDs | 19,101 | Not total registered platform users |
| Train numbers | 540 | Not service departures or trains operated |
| Cancelled bookings | 729 / 19,301 = 3.7770% | Status snapshot; no refund amount |
| Mean reported occupancy | 79.9318% | Arithmetic mean across bookings |

**Concentration.** Delhi - Mumbai has 4,245 bookings and INR 18,405,394 recorded value. Delhi - Howrah has 3,442 bookings and INR 15,444,108. Together they represent 39.83% of accepted bookings and 66.01% of recorded value. Their higher value share can reflect distance, class and passenger mix; it does not establish higher profitability.

**Channel mix.** IRCTC Website has 10,320 bookings (53.47%) and INR 27,703,727 recorded value (54.03%). The app has 6,642 bookings; partners have 2,339. This is a distribution within the supplied sample. Traffic, conversion, channel cost and acquisition data are absent.

**Monthly pattern.** November is the highest booking month: 2,010 records and INR 5,103,595 value. December has 1,815 records, down 9.70% month over month. One year cannot establish recurring seasonality, and the chronology issue below limits any travel-demand claim.

**Tatkal mix.** Tatkal plus Premium Tatkal contributes 5,267 bookings (27.29%) and INR 16,779,958 recorded value (32.72%). No causal surcharge effect is established because the cohorts also vary in class, distance, passenger count and train type.

## The most consequential finding is data quality

11,408 accepted records (59.1057%) have travel before booking. Booking dates cover all of 2025, while travel dates cover only 2 May to 15 July 2025. All August-December booking records therefore fail chronology. The 7,893 valid-date records can support a restricted lead-time sensitivity view, not a corrected annual trend.

Every train number maps to conflicting names, routes, stations, distances and zones. Type and capacity remain consistent. At (train number, travel date) grain, 3,833 of 14,482 groups have conflicting occupancy and 3,113 groups have conflicting delay. Averages across booking rows cannot substantiate capacity utilization or punctuality claims.

No required source cells are missing and all charge components reconcile. Those successful checks do not negate the identity, chronology and operational-grain problems.

## Recommendations as hypotheses

- Reconcile dates and conflicting IDs with the data owner, using source-backed versions and event history. Do not swap dates or discard issues invisibly.
- Validate whether route concentration persists in representative data and matched passenger/class/distance cohorts before allocating commercial effort.
- Obtain status history, actual refunds and settlement facts before reporting recognized revenue or cancellation losses.
- Obtain one validated service-run/class record with offered and occupied seats before measuring utilization or recommending capacity changes.
- Evaluate channel conversion only after joining visits, search outcomes, payment attempts and acquisition costs at appropriate grains.

## What makes the work defensible

The package treats cleaning decisions as explicit business rules, reconciles records and money from source to output, separates booking facts from operational claims, and preserves invalid data for review. It demonstrates data preparation, dimensional thinking, SQL, Python, KPI design, visualization and clear communication. Outcomes are analytical findings and reusable artifacts; no invented revenue uplift or deployed production impact is attached.

For exact field definitions see `DATA_DICTIONARY.md`; source details and reference access evidence are in `SOURCES.md`. The runnable pipeline, tests and project entry points are documented in the root README.

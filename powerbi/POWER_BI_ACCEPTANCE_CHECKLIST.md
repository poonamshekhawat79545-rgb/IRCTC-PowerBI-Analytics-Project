# Power BI Desktop acceptance checklist

**Status: native Desktop checks pending.** This checklist records outcomes after opening the supplied project on Windows. Static JSON, model-reference and embedded-data validation does not complete these checks.

Tester: ____________________  Date: ____________________

Power BI Desktop version: ____________________  Windows version: ____________________

Project/PBIX location: ____________________________________________________________

## Open and refresh

- [ ] Entire project extracted; PBIP, report and semantic-model folders remain together.
- [ ] `powerbi\IRCTC.pbip` opens without project-definition errors in current standard Windows Desktop.
- [ ] **Home → Refresh** completes for Bookings and DimDate with no query, type-conversion or model errors.
- [ ] No source file path or external credentials need configuration for the embedded snapshot.
- [ ] Bookings contains 19,301 rows; DimDate contains 365 unique dates spanning 2025-01-01 to 2025-12-31.
- [ ] `DimDate[date] → Bookings[booking_date]` is active, one-to-many, with single-direction filtering. The travel-date relationship is inactive.

## Baseline reconciliation

Clear slicers and selected chart marks on the page under inspection. Compare exact measure values; formatted cards may round them. If a measure is not displayed on that page, inspect it in a temporary table or DAX query view.

| Measure | Expected | Actual | Pass / fail |
|---|---:|---|---|
| Bookings | 19,301 | | Pending |
| Recorded Booking Value | INR 51,279,303 | | Pending |
| Passengers | 38,528 | | Pending |
| Distinct Users | 19,101 | | Pending |
| Distinct Train Numbers | 540 | | Pending |
| Mean Reported Occupancy Pct | 79.931796% | | Pending |
| Invalid Chronology Records | 11,408 | | Pending |
| Invalid Chronology Rate | 59.105746% | | Pending |
| Valid Lead Time Records | 7,893 | | Pending |
| Mean Valid Lead Time Days | 77.739136 | | Pending |
| Cancelled Bookings | 729 | | Pending |
| Cancellation Rate | 3.777006% | | Pending |

- [ ] Source count reconciliation equals `20,000 − 1 − 698 = 19,301`.
- [ ] Source recorded-value reconciliation equals `53,055,565 − 660 − 1,775,602 = 51,279,303 INR`.
- [ ] Currency is INR; the occupancy fraction is formatted as a percentage exactly once.

## Filter calculations

Start each row below with every slicer cleared. Set the listed selections on one page. Month means **booking month** from the date calendar. Expected values were computed from the supplied accepted CSV, independently of Desktop.

| Test | Slicer selections | Expected bookings | Expected recorded value (INR) | Additional expected result |
|---|---|---:|---:|---|
| A | Status: Confirmed | 15,864 | 42,171,186 | 31,643 passengers; 15,727 users; cancellation rate 0% |
| B | Month: 2025-06; Channel: IRCTC App; Route: Delhi - Mumbai | 119 | 516,988 | 247 passengers; 119 users; 108 train numbers; 42 valid lead records |
| C | Month: 2025-11 | 2,010 | 5,103,595 | 2,010 invalid chronology records; 0 valid lead records; mean valid lead time blank |
| D | Month: 2025-05; Channel: IRCTC Website; Type: Tatkal; Status: Waitlisted (WL); Route: Mumbai - Pune | 1 | 116 | 1 passenger, user and train number; occupancy 69.0% |
| E | Month: 2025-01; Channel: IRCTC App; Type: Premium Tatkal; Status: Cancelled; Route: Hyderabad - Bengaluru | 0 | 0 | Counts 0; occupancy and denominator-based averages/rates blank |

- [ ] Test A passes, including zero cancellation rate for a nonempty Confirmed-only cohort.
- [ ] Test B passes, proving multiple slicers intersect correctly.
- [ ] Test C passes, keeping invalid chronology in booking totals and excluding it from valid lead time.
- [ ] Test D passes, including readable small currency values.
- [ ] Test E passes without misleading averages or visual errors.
- [ ] Clear selections and confirm every baseline measure returns to its original value.
- [ ] Full-source reconciliation measures stay fixed during these filter tests.
- [ ] Page slicers operate locally: changing one page does not silently synchronize selections to another page.
- [ ] Selecting and clearing chart marks filters other data visuals without changing the source reconciliation.

## Visual and report review

- [ ] **Booking overview**, **Routes & customers**, and **Data quality** pages are present and readable.
- [ ] Cards, charts, legends, slicers, tables and explanatory text render without missing fields or unsupported-visual errors.
- [ ] No titles, labels, currency values or table columns overlap or clip at the normal report viewing size.
- [ ] Booking months sort chronologically; route rankings and status/channel labels match the selected cohort.
- [ ] Source reconciliation is visually distinguished from filtered measures.
- [ ] Wording identifies recorded booking value, distinct train numbers and booking-record occupancy accurately.
- [ ] The synthetic-data scope and chronology limitations are visible enough to explain during a portfolio presentation.

## Save, reopen and record evidence

- [ ] Save a Power BI file as `IRCTC_Business_Insights.pbix` using **File → Save as**.
- [ ] Close Desktop and reopen the saved `.pbix` successfully.
- [ ] All three pages and imported data remain available after reopening.
- [ ] Recheck baseline totals and filter Test B in the reopened PBIX.
- [ ] Refresh the reopened PBIX successfully without a source-path or credentials prompt.
- [ ] Save a screenshot of each final report page and record any adjustments made during native validation.

Final PBIX filename: ____________________________________________________________

Final outcome: **Pending / Pass / Fail**

Issues, exact error messages and fixes:

________________________________________________________________________________

________________________________________________________________________________

________________________________________________________________________________

Only mark native acceptance as passed after the above actions have been performed in Power BI Desktop. Keep the source PBIP project alongside the PBIX for future editing and reproducible rebuilds.

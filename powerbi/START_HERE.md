# Open your native Power BI project

Start with **[IRCTC.pbip](IRCTC.pbip)** in Power BI Desktop on Windows. The report and semantic model are already authored. The accepted booking data is embedded, so you do not need to change a path, connect an account, or paste the import query and measures.

## First open

1. **Extract the entire ZIP** to a short local folder, such as `C:\IRCTC_Project`. Keep `IRCTC.pbip`, `IRCTC.Report`, and `IRCTC.SemanticModel` together inside the `powerbi` folder.
2. Use a **current standard Power BI Desktop for Windows**. The edition optimized for Power BI Report Server does not support PBIP projects. Open `powerbi\IRCTC.pbip`; opening `IRCTC.Report\definition.pbir` is an alternative supported entry point. [Microsoft's project documentation](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
3. Select **Home → Refresh** and wait until both embedded tables finish loading. The delivered project has model definitions and embedded source bytes but no Desktop data cache. Its initial visuals may be empty until this refresh completes. [Microsoft's semantic model documentation](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)
4. Clear slicers and any selected chart marks on each page. Check the baseline below, then follow [the acceptance checklist](POWER_BI_ACCEPTANCE_CHECKLIST.md).
5. Select **File → Save as**, choose the **Power BI file (`.pbix`)** format, and save as `IRCTC_Business_Insights.pbix`. Close and reopen that file to confirm the report and imported data are saved. PBIP-to-PBIX conversion is performed by Desktop's Save As operation. [Microsoft's conversion guidance](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview#frequently-asked-questions)

## Baseline after refresh

Use the report's cards/tables or the named measures in the model. Currency cards may show rounded display units; inspect the exact value when checking reconciliation.

| Measure | Expected result with all filters cleared |
|---|---:|
| Bookings | 19,301 |
| Recorded Booking Value | INR 51,279,303 |
| Passengers | 38,528 |
| Distinct Users | 19,101 |
| Distinct Train Numbers | 540 |
| Mean Reported Occupancy Pct | 79.931796% before display rounding |
| Invalid Chronology Records | 11,408 |
| Valid Lead Time Records | 7,893 |

Source reconciliation is **20,000 − 1 − 698 = 19,301 records** and **INR 53,055,565 − 660 − 1,775,602 = 51,279,303**. The nine full-source reconciliation measures deliberately stay fixed when you filter the report.

## Explore the report

- **Booking overview:** booking demand, recorded value, channel/type mix, route activity and status.
- **Routes & customers:** route comparisons, passenger/user activity, cancellations and booking mix.
- **Data quality:** source reconciliation, chronology anomalies and metric definitions.

Each page has its own booking-month, channel, booking-type, status and route slicers. They combine within that page; they are **not synchronized between pages**. Clear every slicer on the current page before testing a new selection. Clicking a chart mark or table row also filters other data visuals. Valid lead-time measures are on the Data quality page.

Concrete filter checks, calculated independently from `data/processed/bookings_clean.csv`, are included in the acceptance checklist. The processed summary CSVs and `reports/metrics.json` provide further comparison values.

## What the figures mean

Recorded booking value includes all selected statuses, including cancelled and waitlisted records; it is not recognized revenue, profit or settled cash. Passenger counts describe bookings, not verified completed journeys. Distinct train numbers do not measure operated services. Occupancy and delay are averages of supplied booking-record fields because values conflict within train-date groups. Negative booking lead times remain in booking totals but are excluded from valid lead-time measures.

This is a synthetic educational portfolio dataset. The model isolates one exact duplicate and every member of 349 conflicting booking-ID groups before reporting.

## Validation status

The delivered definitions have been checked structurally, and the embedded booking CSV has been decoded and matched byte-for-byte to the accepted dataset. Field types, keys, date coverage, relationships and DAX references were checked. See `IRCTC.SemanticModel/MODEL_VERIFICATION.json` and the project's QA reports for the checks actually performed.

**Power BI Desktop opening, Power Query execution, DAX evaluation, visual rendering and PBIX saving have not been performed on this macOS host.** Those Windows outcomes remain pending in the acceptance checklist. A successful static check is not evidence that Desktop has executed the project.

## Refreshing and rebuilding

**Refresh loads the embedded snapshot.** Changing the external CSV alone does not change this Power BI model.

To rebuild the embedded snapshot after an intentional source update, close the project in Desktop, preserve your report edits, and run these commands from the main project folder using Python 3.10 or later:

```sh
python src/pipeline.py
python src/build_powerbi_model.py
```

Review the new exception files and controls before reopening and refreshing the project. Repeat the acceptance checks and save a new PBIX. Original baseline values and filter expectations in this document apply only to the supplied dataset. Independently update regression expectations, report text and presentation snapshots when using a replacement dataset. The main project guide describes report-definition and other presentation rebuild steps.

If Desktop reports an error, retain the exact message and file location, together with your Desktop version. Confirm the whole project was extracted and the normal Windows Desktop edition is current before investigating the named definition or query.

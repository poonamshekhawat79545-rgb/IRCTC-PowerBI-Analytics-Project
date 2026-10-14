# Validation summary

Validated against the supplied synthetic source. A passing processing check does not make its unresolved source anomalies valid.

| Area | Performed | Result |
|---|---|---|
| Source and cleaning | Exact duplicates, conflicting IDs, missing values, typed fields, ranges, dates and charge components | Source retained; 1 exact duplicate removed; all 698 conflicting-ID rows quarantined |
| Reconciliation | Row counts, INR amounts, passengers, dimension keys, aggregate totals and SQLite integrity | 24 checks passed |
| Python tests | 20 policy, boundary, source, SQL and artifact-contract tests | Passed |
| Reproducibility | Rebuilt 28 generated CSV, JSON, SQLite and schema outputs | Byte-identical outputs for the same source |
| SQL | All 18 analytical queries executed against the read-only SQLite database | Passed |
| Notebook | All 9 code cells executed with saved output; no error outputs | Passed |
| Dashboard calculations | Actual inline application script executed in Node with an in-memory document model; 36 independent CSV filter scenarios | Counts, values, passengers, distinct users/trains, chronology denominators and occupancy agree |
| Dashboard interaction logic | Navigation state, route search, reset, trend metric, modal state, empty cohort and generated CSV | 38 total logic checks passed, including the 36 cohorts |
| Excel formulas | Headline, 12 monthly and 8 route controls, valid lead-time calculations and a temporary source-value change | Recalculated correctly; source change restored |
| Excel export | Five sheets, all 19,301 accepted rows in 16 selected fields, 248 formulas, three native charts, cached values, dates and panes | No cached formula errors; nine reconciliation differences are zero |
| Excel appearance | Every sheet's relevant opening/content ranges rendered and inspected | Layout reviewed; full 42-field record remains in the clean CSV |
| PDF | Six pages rendered and visually inspected; figures independently recalculated from accepted CSV | Passed |
| Native Power BI project | Microsoft schemas, descriptors, theme references, 60 visual query roles/bindings, interactions, page geometry and model references | 341 structural/data checks passed, including 69 official schema documents; three pages, 38 measures |
| Power BI embedded source | Decoded embedded CSV bytes, typed values, calendar continuity, dimension relationships and independent control totals | All 19,301 accepted rows match the cleaned source; two import tables and two date relationships checked |
| Power Query syntax | Microsoft's `@microsoft/powerquery-parser` 2.0.0 parsed both native partition queries and the optional CSV import | Three valid queries passed; deliberately invalid M was rejected. This does not evaluate M or refresh the model |

## Material validation limits

- **Browser:** Local HTML navigation was blocked by browser security policy. Dashboard calculations were tested without a browser. Actual browser layout, mobile rendering, native events and download UI behavior were not visually verified.
- **Excel:** Recalculation and rendering used the spreadsheet generation engine. Microsoft Excel desktop was not exercised. The workbook uses fixed snapshot ranges; distinct users and train numbers are documented refresh-time controls rather than dynamic distinct-count formulas.
- **Power BI:** A native `.pbip` report and semantic model are delivered. No `.pbix` is claimed. Opening, Power Query refresh, DAX evaluation, actual visual rendering and PBIX saving/reopening require Power BI Desktop on Windows and remain untested here. Static schemas allow some arbitrary visual formatting values, so schema validity does not prove rendering. The acceptance checklist records those remaining checks.
- **Source:** 11,408 accepted records (59.11%) have booking dates after travel. These remain flagged and count toward descriptive booking totals. Occupancy and delay conflict within train/date groups. No test establishes real IRCTC operations, causal effects or recognized revenue.

## Headline control reconciliation

| Control | Expected |
|---|---:|
| Accepted booking rows | 19,301 |
| Recorded booking value, INR | 51,279,303 |
| Recorded passengers | 38,528 |
| Distinct user IDs | 19,101 |
| Distinct train numbers | 540 |
| Invalid chronology | 11,408 |
| Valid lead-time denominator | 7,893 |
| Mean supplied occupancy | 79.931796% |
| Cancelled booking records | 729 |

Machine-readable evidence is in `validation.json`, `dashboard_logic_validation.json` and `workbook_validation.json`. Reproduction commands are in the project README. Regression controls intentionally describe the original supplied dataset and must be independently updated for any replacement source.

# Interview and portfolio guide

## Five-minute walkthrough

**0:00-0:40 | Business question.** “I built an educational IRCTC booking analysis to explain booking and value distribution across routes, time and channels. The first challenge was defining what each number could actually claim.” Name the supplied dataset and credit the linked DataCliq inspiration.

**0:40-1:30 | Cleaning decisions.** Show the reconciliation: 20,000 source rows to 19,301 accepted IDs. Explain the one identical repeat and the 698 records from 349 conflicting-ID groups. Keeping both would inflate value; choosing one date without evidence would invent a correction.

**1:30-2:20 | Analytical model.** Show the booking fact and date/route/train dimensions. Explain why a train dimension includes only number, type and capacity: names and routes conflict. Describe a many-to-one join and demonstrate that sums do not change after joins.

**2:20-3:20 | Findings.** Show INR 51.28m recorded booking value and 19,301 accepted bookings. Demonstrate one dashboard filter. Explain that two routes account for 66.01% of recorded value, while the website has 53.47% of bookings. Separate observations from suggested investigations.

**3:20-4:20 | Data-quality finding.** Show the 59.11% chronology issue. Explain that August-December booking dates occur after every travel date. State why valid-lead analysis uses only 7,893 records and cannot replace the full-year cohort.

**4:20-5:00 | Validation and next step.** Show the validation report and reconciliation. Explain that passing checks certifies the processing controls, not source accuracy. End with the request for source event history, service-run keys and refund data needed to support operational decisions.

## Three truthful resume bullets

Use these only after you have reviewed the package, reproduced the workflow and can explain it independently. Describe your own contribution accurately and acknowledge tool assistance if asked.

- Built a reproducible educational booking-analysis project spanning Python, SQLite, an interactive dashboard and Excel, with documented KPIs for 19,301 accepted booking records and INR 51.28m in recorded booking value.
- Implemented auditable identity controls that removed one exact duplicate and quarantined 698 conflicting records, while reconciling counts and booking value to the 20,000-row input.
- Identified invalid chronology in 59.11% of accepted records and train-metadata inconsistencies; designed explicit flags and restricted lead-time analysis to prevent unsupported utilization and revenue claims.

The native Power BI project includes three authored pages, 60 visuals, 38 measures and an embedded import model. After completing the Windows acceptance checklist and being able to explain the model, you can describe the dashboard as a Power BI implementation. Before that, describe it as an authored, structurally checked native project awaiting Desktop verification. Do not claim “increased revenue,” “improved efficiency by X%,” “used by IRCTC” or “deployed in production” without evidence.

After successful Desktop verification, an alternative first bullet is: “Built a three-page Power BI portfolio dashboard with 38 measures, page filters and auditable Python/SQL preparation for 19,301 synthetic booking records representing INR 51.28m in recorded value.” Use it only when you can demonstrate the report and explain your own contribution.

## Questions you should be able to answer

| Interview question | Defensible answer |
|---|---|
| What is the grain? | One accepted booking ID per fact row. A row is not one passenger or one service run. |
| Why not drop all repeated IDs? | First remove identical repeats, then quarantine every distinct conflicting version. Repeated users are valid and must not be deduplicated. |
| Why quarantine instead of keeping latest? | No trustworthy version timestamp or source precedence establishes which booking date is correct. |
| Why retain negative lead times? | They remain useful as flagged descriptive booking records. Only valid lead-time measures exclude them; the exclusion has a disclosed denominator. |
| What does the money measure? | Source Total_Revenue_INR renamed recorded booking value, including every retained status. Refunds, settlements, costs and recognized revenue are missing. |
| Why not call 540 trains operated? | Train numbers are identifiers, not departures. They map to multiple names/routes and lack verified run keys. |
| Why not average occupancy by train? | Train/date groups conflict and coverage is booking-based. A true load factor requires occupied and offered seats per validated service/class grain. |
| How do you avoid double counting after joins? | Dimension keys are unique, joins are many-to-one, and fact counts/value totals must reconcile before and after the join. |
| Why are distinct users non-additive? | A user can appear in several months or channels. Summing subgroup distinct counts can count the same user more than once. |
| How do you aggregate averages? | Recompute from the filtered fact rows, or weight each mean by its matching record denominator. Do not take a simple mean of differently sized group means. |
| How should MoM work? | Use one complete booking calendar month and the immediately preceding complete month. Return blank when prior data is unavailable; do not compare a full-year total with one prior month. |
| Is website performance better? | Website has a larger share in this sample. Conversion or profitability requires exposure, costs and matched cohorts; share alone cannot establish superiority. |
| Can you forecast demand? | This single-year, inconsistent sample does not support a reliable operational forecast. Repair source coverage and collect a longer validated history first. |
| What did testing prove? | Processing rules, row/value accounting, unique IDs, valid relationships and aggregate consistency. It did not prove official provenance or operational truth. |
| What would you do next? | Obtain authoritative event history and service-run keys; validate representative coverage; then test route/channel hypotheses with suitable denominators. |

## Practical demonstration checklist

1. Rebuild the pipeline from the preserved source and run the existing tests.
2. Compare the accepted totals with the SQLite and workbook results.
3. Apply a channel or route filter and explain the changed denominator.
4. Open one quarantined-ID pair and explain why both versions are unresolved.
5. Explain the date coverage, occupancy weighting and the distinction between recorded booking value and revenue.
6. Present one testable recommendation and name the additional data required to evaluate it.

The best interview story is the analytical judgment you can defend. A polished dashboard helps, but the reconciliation and measurement limitations are central to this project.

# Native Power BI implementation

Start with [START_HERE.md](START_HERE.md). Open **IRCTC.pbip** in current Power BI Desktop for Windows, refresh the embedded data, inspect the three pages and save a `.pbix`. The report is a native PBIR project bound by a relative path to its semantic model.

## Project structure

| Item | Purpose |
|---|---|
| `IRCTC.pbip` | Launcher referencing the adjacent report folder |
| `IRCTC.Report/definition.pbir` | Relative binding to `../IRCTC.SemanticModel` |
| `IRCTC.Report/definition/` | Three pages and 60 native visuals using Microsoft's public PBIR JSON schemas |
| `IRCTC.Report/StaticResources/` | Packaged Microsoft base theme and supplied six-color custom palette |
| `IRCTC.SemanticModel/definition.pbism` | Supported model.bim format descriptor |
| `IRCTC.SemanticModel/model.bim` | Two import tables, 38 measures, two relationships and embedded CSV source bytes |

The model has 42 cleaned booking columns and a continuous 365-day calendar. The active relationship filters bookings by booking date; the travel-date relationship is inactive. Both are single-direction, one-to-many relationships. The calendar has month/day sort columns and a year/month/date hierarchy. The flat booking table retains route, channel, class and status attributes. The separate SQLite model demonstrates date, route and train dimensions. Train names/routes cannot be treated as stable one-row-per-number attributes.

Power Query decompresses embedded GZip/Base64 CSV snapshots and explicitly applies types. It requires no credentials, external file path, web connection or gateway. No Desktop data cache is supplied: **Refresh is required on first open**. Blank valid-lead-time values remain null. Core measures respond to filter context; the nine source reconciliation measures are fixed snapshot controls.

## Report pages

| Page | Content |
|---|---|
| Booking overview | Five KPI cards; monthly bookings; booking type/channel recorded value; all eight routes ranked by bookings; value by status |
| Routes & customers | Passenger, average-value, cancellation and repeat-user cards; route comparison table; class, train-type and payment mix |
| Data quality | Fixed source reconciliation; filtered chronology and valid-lead metrics; chronology trend; route-level conflict counts and measurement limits |

The canvas is 1600 × 1000. The design uses the supplied blue/red palette, pale backgrounds, native cards, line/bar charts, tables, dropdown slicers and explanatory text. It adapts the source template's visual direction while correcting metric names and removing placeholders.

Five page-local slicers select booking month, channel, booking type, status and route. They are not synchronized between pages. Explicit page interactions make slicer and chart/table selections filter other data visuals. Clear chart selections as well as slicers when checking totals. Sorting uses the chronological `year_month` key for trends and descending measures for comparisons. Route share uses `ALLSELECTED` to retain the selected route population. Native tooltips and on-page definitions provide context. Baseline and five concrete filter scenarios are in the [Windows acceptance checklist](POWER_BI_ACCEPTANCE_CHECKLIST.md).

## Rebuild and verify

From the complete portfolio root, with Desktop closed:

```sh
python3 src/pipeline.py
python3 src/build_powerbi_model.py
python3 src/build_powerbi_report.py
python3 -m pip install jsonschema
python3 src/validate_powerbi_project.py
```

The builders replace the model snapshot and generated pages. Preserve manual Power BI changes first. The validator downloads only public Microsoft JSON schemas into a local cache. It checks schemas, project/theme references, model bindings, native query roles, visual geometry, interactions and embedded source equality. Results are saved in `../reports/powerbi_validation.json`. These checks do not execute the Power BI engine.

`Import_Bookings.pq`, `Date_Table.dax` and `Measures.dax` remain as learning/reference files for a manual CSV-based build. They are not steps required to open the delivered project. The complete set of 38 measures is in `model.bim`; the standalone DAX file contains core measures from which the builder adds quality controls and mix measures.

The embedded snapshot, static report text and acceptance expectations belong to this supplied dataset. A source replacement requires independent reconciliation and review of all explanatory text, test expectations, PDF and workbook snapshots. Ordinary Desktop Refresh loads the embedded snapshot; it does not reread the external CSV.

## Verification boundary and references

Official schema checks, source-byte reconciliation and independent static audits passed. This Mac environment has not opened, refreshed or rendered the project in Desktop. **Windows Power Query/DAX execution, visual inspection and saving/reopening `.pbix` remain pending.** Record those outcomes in the checklist before describing the dashboard as Desktop-verified.

Microsoft's Power Query parser 2.0.0 also accepted both native partition queries and the optional CSV import; a deliberately invalid query was rejected. This is a syntax check, not M evaluation. Its saved evidence is `../reports/powerquery_syntax_validation.json`. To repeat it from the complete portfolio, install `@microsoft/powerquery-parser@2.0.0` with npm and run `node tests/test_powerquery_syntax.cjs`.

- [Microsoft Power BI projects and PBIX conversion](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
- [Native PBIR report folders](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report)
- [Semantic model project folders](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset)
- [Microsoft public JSON schemas](https://github.com/microsoft/json-schemas)
- [Microsoft report-authoring format references](https://github.com/microsoft/skills-for-fabric/tree/main/skills/powerbi-report-cli/references/authoring)

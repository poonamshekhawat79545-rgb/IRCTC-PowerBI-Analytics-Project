# Native semantic model

This folder contains a Power BI semantic model definition in the supported TMSL `model.bim` format. `definition.pbism` version 1.0 selects that format. The parent report refers to this folder by a relative path.

The `Bookings` table contains **19,301 accepted records**, all **42** cleaned columns and **38 explicit measures**. `DimDate` contains **365** continuous calendar dates. The booking-date relationship is active and the travel-date relationship is inactive. The calendar has a Year / Month / Date hierarchy and month/day sorting.

Both tables use embedded, compressed CSV snapshots. The queries have no local file path, web request, credentials or gateway dependency. On first open in Power BI Desktop for Windows, select **Refresh** to materialize the embedded tables, check the figures, and use **Save As** if a `.pbix` file is needed. No `cache.abf` data cache is included.

Baseline recorded booking value is **INR 51,279,303**. All statuses are retained. Full-source reconciliation measures are fixed snapshot controls; booking and quality measures otherwise follow report filter context. Occupancy and delay describe booking-record fields and do not establish service performance. This is a synthetic educational dataset.

The builder passed **12 static and embedded-data checks**, recorded in `MODEL_VERIFICATION.json`. Payload decompression recovers the accepted CSV byte-for-byte; types, keys, relationships, date continuity, sorting and DAX references were checked. These checks do not compile DAX, execute Power Query M or confirm Power BI rendering. Native execution remains a Windows Desktop verification step.

To rebuild after updating the pipeline outputs, run `python3 src/build_powerbi_model.py` from the main project folder, then refresh the project in Desktop. The builder has no third-party Python dependency. Close Desktop before replacing its model files.

Official references: [Power BI semantic model folder](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset), [TMSL table objects](https://learn.microsoft.com/en-us/analysis-services/tmsl/tables-object-tmsl), [relationships](https://learn.microsoft.com/en-us/analysis-services/tmsl/relationships-object-tmsl), and [Power Query decompression](https://learn.microsoft.com/en-us/powerquery-m/binary-decompress).

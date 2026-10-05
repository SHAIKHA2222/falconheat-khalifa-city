# FalconHeat v4.3 — Final Presentation Polish

- Fixed duplicated hero wording (`summer-matched season-matched`).
- Rebuilt Priority Queue HTML rendering so Moderate/Low rows no longer leak stray `</div>` text.
- Made AOI provenance explicit: `Curated study polygon · not an official municipal boundary`.
- Added a compact **Data integrity status** panel showing core EO, historical Sentinel-2, WorldPop and AOI status.
- Standardized WorldPop wording to **estimated residents**.
- Clarified the Scenario Lab surface slider as an assumed effective exposed-surface reduction, not a literal update to WorldCover 2021.
- Preserved the v4.2 conservative temporal-change logic and no-synthetic-fallback behavior.

# FalconHeat v4.2 — Scientific Review Correction

- Reviewed the generated Khalifa City CSV rather than only the interface.
- Found that all 12 polygons had **negative ΔNDBI** in the selected 2021→2026 comparison, so the dashboard had no positive NDBI expansion signal.
- Found that the largest NDVI decrease was only about `-0.011`, while the previous relative normalization could award a full 15 change points to the largest small decrease.
- Added a transparent **±0.02 PoC tolerance** for single-season NDVI/NDBI change. Differences inside the band are now treated as inconclusive instead of being amplified.
- Negative ΔNDBI is never described as urban expansion.
- The change component now uses only NDVI loss beyond `-0.02` and positive NDBI increase beyond `+0.02`.
- Added a dashboard warning when no positive NDBI increase is detected.
- Renamed temporal output to **change evidence** rather than implying proven urban expansion.
- Improved Exposure KPI wording and layout.
- Added an explicit Scenario Lab warning that large score changes are sensitivity results from a relative index, not predicted physical cooling.
- Version-specific findings should be regenerated through `run_analysis()` from the cached real-data CSV; no synthetic values are introduced.

# FalconHeat v4.1 — Competition Polish

- Reworked the sidebar priority equation so it no longer clips on normal laptop widths.
- Replaced cramped six-column executive metrics with two clean rows of three.
- Replaced the mathematically uninformative median heat anomaly with the **hottest surface anomaly**.
- Renamed population metrics to **estimated residents** and explicitly identifies WorldPop as a model estimate.
- Standardized visible area names to `Kxx · near <local reference>` so analytical polygons are not confused with official sector boundaries.
- Added an automatic **Executive Insight** sentence for the top-priority polygon.
- Added automatic **Why this area?** explanations based on the two largest score contributions.
- Added short "why" explanations to High/Very High hotspot queue cards.
- Reworked the Explainability KPIs into two rows so values remain readable.
- Added AOI provenance as a source card and moved the optional GeoJSON upload into a compact sidebar expander.
- Cleaned urban-change charts, Scenario Lab selection and export tables to use the competition-safe analysis-polygon names.

# FalconHeat v4.0 — Advanced Real-EO

- Added summer-matched Sentinel-2 2021→2026 change analysis.
- Added WorldPop 2026 polygon population exposure.
- Added explainable five-driver priority model.
- Added dynamic weight redistribution when optional real sources are unavailable.
- Added surface heat anomaly.
- Added evidence-completeness confidence.
- Added Scenario Lab.
- Added Priority / Surface Temperature / Population / Vegetation Change map layers.
- Added optional same-track Sentinel-1 GRD VV change diagnostic.
- Added custom Khalifa City GeoJSON AOI uploader/override.
- Added provenance and analyzed CSV download.
- Added advanced reproducible notebook and methodology/judging docs.
- Preserved strict no-synthetic-fallback behavior.

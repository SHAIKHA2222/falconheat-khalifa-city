# Submission review — 10 October 2026

## Completed checks

- The listed Landsat item and all six listed Sentinel-2 items resolved from the Microsoft Planetary Computer STAC catalog; returned acquisition dates match the published metadata.
- Landsat item's thermal scale/offset matches the code's fallback (0.00341802 and 149 K).
- Recalculated snapshot scores, contributions, population totals and zero-intervention scenarios were checked.
- Bundled derived scores were synchronized with the current model. Source indicator values were not replaced or invented.
- Dashboard runtime, all four map-layer selections, empty filters, maximum-score filters and zero-intervention controls were exercised with Streamlit AppTest.
- CSV source rows and the runtime use the same model. The JSON export now includes score formula, class ranges, normalization and weights.

## Corrections

- Shorter, accurate study-boundary disclosure; explicit Khalifa City scope.
- Correct 0–100 formula including its factor of 100.
- Directional change-stress language: negative NDBI change is not an urban-expansion flag.
- Consistent evidence-completeness labels; no implication of validated accuracy.
- Filtered priority queue, empty-state guidance and map legends.
- Unique map component keys prevent a duplicate-key crash when selecting the population layer.
- Correct highest-polygon-median temperature label.
- Missing/non-finite indicator validation and threshold-boundary consistency.
- Temporary uploaded GeoTIFF cleanup.
- Offline-first notebook; remote rebuild writes separately.
- README aligns with the published snapshot and distinguishes the optional deep-learning experiment.

## Remaining scientific and submission limits

This review did not re-download and independently reproduce all EO raster statistics or the WorldPop polygon totals. The source inputs and their provenance are the team's existing published snapshot. No new field validation, model training or accuracy evaluation was performed.

Before claiming measured urban expansion, validate Sentinel-2 radiometric harmonization across processing baselines, avoid overweighting overlapping tiles, compare multiple dates, and validate against reference labels. Scene footprint coverage is not the same as usable pixel coverage.

The current evidence-completeness heuristic uses scene-level metadata and clipping fractions, with a default partial score for unknown cloud metadata. It is not an independent accuracy or uncertainty measure.

The app does not implement a trained deep-learning model, use 813 imagery in scoring, or supply validated heat-health predictions. Its current value is an explainable planning-priority PoC. Organizer requirements for 813/SAR use and required deliverables must be checked separately; they were not provided as an authoritative submission checklist for this review.

The presentation PDF and any separate competition submission form are outside this repository review. Neither submission nor acceptance is implied by this commit.

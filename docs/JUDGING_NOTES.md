# FalconHeat Judging Notes

## 30-second value proposition
FalconHeat turns real satellite observations into an explainable urban heat
decision system for Khalifa City. Instead of only showing where the surface is
hot, it combines current heat, vegetation, built-up land, recent land-surface
change and population exposure, then explains *why* each area is prioritized and
lets planners test intervention scenarios.

## Strongest points to demonstrate live
1. Show the exact Khalifa City AOI and clipped analysis polygons.
2. Switch map layer from Priority -> Surface temperature -> Vegetation change -> Population.
3. Click a high-priority polygon and show its source-derived values.
4. Show the five-driver score contribution chart.
5. Open Urban Change and explain the 2021 vs 2026 seasonal comparison.
6. Open Exposure and show how many estimated people overlap with priority areas.
7. Use Scenario Lab to reduce assumed LST / increase NDVI and show the score change.
8. Open Evidence & Export and show actual scene IDs and downloadable provenance.
9. If you have the organizer's 813 GeoTIFF, load it in the 813 Challenge Imagery Lab and show its metadata/quicklook.

## Safe claims
- "real Earth-observation inputs"
- "summer-matched 2021-to-2026 Sentinel-2 change signals"
- "Landsat-derived land-surface temperature"
- "WorldPop model-estimated population exposure"
- "explainable relative planning-priority index"
- "decision-support sensitivity scenario"

## Claims to avoid
- "air temperature is 53°C"
- "this is a medical heat-risk score"
- "this polygon gained X square kilometres of buildings" based only on NDBI
- "WorldPop is the official population count"
- "Scenario Lab predicts the exact cooling effect"
- "Sentinel-1 diagnostic is calibrated RTC backscatter"

## Judge question: Where is the AI?
Answer:
FalconHeat is an AI-assisted geospatial decision system, but the competition
version intentionally keeps the core decision engine interpretable rather than
hiding it in a black box. The main output is based on real EO feature extraction,
change analysis and explainable multi-factor scoring. The repository also
contains an optional deep-learning segmentation lab, but we do not use generic
DL classes as scientific evidence until an EO-specific model is trained and
validated.

## Judge question: Why these weights?
Answer:
The weights are PoC planning assumptions, not medical thresholds. Temperature
gets the largest weight because FalconHeat is prioritizing heat-mitigation;
built-up land, low vegetation, population exposure and recent change add context.
The dashboard exposes every contribution and effective weight so the method can
be validated or replaced by planners.

## Judge question: What would you do next?
- official municipality boundaries / parcels;
- field temperature and weather-station validation;
- official demographic/vulnerability layers;
- EO-trained semantic segmentation/change-detection model;
- multi-year seasonal composites rather than one selected day;
- intervention effectiveness calibration using observed projects.

## Current temporal finding in the reviewed run
Do **not** tell judges that FalconHeat detected built-up expansion in every polygon.

The reviewed 2021→2026 comparison showed no positive NDBI change in the 12 analysis polygons. The honest competition statement is:

> "In this selected summer-matched comparison, FalconHeat did not detect a positive NDBI expansion signal. Several polygons had small NDVI decreases, but v4.2 treats changes inside ±0.02 as inconclusive rather than amplifying them. This is why the Urban Change tab is evidence, not a claim of cadastral growth."

That honesty is a strength: FalconHeat reports what the data supports instead of forcing a growth narrative.


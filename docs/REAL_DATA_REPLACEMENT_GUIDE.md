# FalconHeat Real Earth-Observation Workflow — Advanced v4

This file summarizes the production path used by the Streamlit dashboard.

1. Resolve the Khalifa City AOI:
   - custom `data/khalifa_city_boundary.geojson`, else
   - OpenStreetMap/Nominatim, else
   - conservative fallback polygon.
2. Divide the AOI into clipped analysis polygons.
3. Query current Sentinel-2 Level-2A (Jul–Sep 2026), mosaic intersecting tiles from one acquisition day, cloud-mask with SCL, derive NDVI/NDBI.
4. Query summer-matched historical Sentinel-2 Level-2A (Jul–Sep 2021), derive NDVI/NDBI and 2021→2026 change.
5. Query Landsat Collection 2 Level-2 (Jul–Sep 2026), QA-mask and derive polygon-median surface temperature.
6. Query ESA WorldCover 2021 and compute class-50 built-up share.
7. Query WorldPop Global2 API v2 (2026, 100 m) for population inside each polygon.
8. Optionally query Sentinel-1 GRD for a matched 2021/2026 same-track VV amplitude-change diagnostic.
9. Calculate evidence-completeness confidence.
10. Calculate the explainable planning-priority index.
11. Cache the measured/derived indicators and provenance JSON.
12. Expose source trace, contribution breakdown, scenario analysis and downloadable outputs in the dashboard.

## Priority model

`H = 0.35T + 0.20B + 0.15V + 0.15P + 0.15C`

- T = normalized Landsat LST
- B = normalized WorldCover built-up share
- V = normalized low vegetation
- P = log-normalized WorldPop exposure
- C = normalized urban-change stress from positive NDBI gain + vegetation loss

Optional missing layers are not imputed; their weights are redistributed across available measured components.

## Scientific caution

- LST is surface temperature, not air temperature.
- One-season 2021→2026 change is not a long-term climate trend.
- NDBI can respond to bright/bare surfaces as well as built-up surfaces.
- WorldCover 2021 and WorldPop 2026 have different reference dates.
- Population is model-estimated.
- Sentinel-1 GRD evidence is diagnostic only and excluded from the priority score.
- The 0–100 result is a relative planning-priority ranking, not a validated heat-health standard.

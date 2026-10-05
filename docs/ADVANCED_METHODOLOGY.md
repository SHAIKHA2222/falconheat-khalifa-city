# FalconHeat Advanced Methodology

## 1. Study area
FalconHeat operates on clipped Khalifa City polygons rather than a rectangular grid.

Boundary precedence:
1. user-supplied `data/khalifa_city_boundary.geojson`;
2. OpenStreetMap/Nominatim polygon;
3. conservative built-in fallback.

All raster statistics are masked to each clipped analysis polygon.

## 2. Current heat
Source: Landsat Collection 2 Level-2, summer 2026.

Processing:
- use the Level-2 surface-temperature (`lwir11`) asset;
- apply STAC raster scale/offset;
- convert kelvin to °C;
- mask QA_PIXEL fill, cloud, cirrus, cloud shadow, snow;
- calculate the polygon median.

`surface_heat_anomaly_c = cell_LST - median_LST_across_AOI`

This anomaly is descriptive, not a climatological anomaly.

## 3. Current vegetation and built-up signal
Source: Sentinel-2 Level-2A, summer 2026.

- NDVI = (B08 - B04) / (B08 + B04)
- NDBI = (B11 - B08) / (B11 + B08)

The Scene Classification Layer removes no-data, saturated pixels, cloud shadow,
medium/high cloud, cirrus and snow/ice.

## 4. Historical change
Source: Sentinel-2 Level-2A, summer 2021.

The same Jul–Sep seasonal window is used in 2021 and 2026.

Per polygon:
- ΔNDVI = NDVI_2026 - NDVI_2021
- ΔNDBI = NDBI_2026 - NDBI_2021
- raw vegetation decrease = max(0, -ΔNDVI)
- raw positive NDBI change = max(0, ΔNDBI)

For the **priority score only**, v4.2 applies a transparent PoC tolerance:
- vegetation-loss contribution begins only when ΔNDVI <= -0.02;
- NDBI-change contribution begins only when ΔNDBI >= +0.02.

Changes inside ±0.02 remain displayed but are treated as inconclusive for scoring.
These are spectral change signals, not exact building-area measurements, and the
±0.02 tolerance is a conservative PoC rule rather than a universal threshold.

## 5. Structural built-up share
Source: ESA WorldCover 2021.

`built_up = count(class_50) / count(valid_landcover_pixels)`

WorldCover is treated as a structural baseline only.

## 6. Population exposure
Source: WorldPop Global2 API v2, year 2026, 100 m.

WorldPop receives each analysis polygon and returns an estimated total population.
FalconHeat also calculates polygon area and approximate population density.

Population values are estimates, not census counts.

## 7. Optional Sentinel-1 evidence
Source: Sentinel-1 GRD.

FalconHeat attempts to match 2021 and 2026 scenes using the same relative orbit,
orbit state and IW mode. It derives a median VV amplitude change in dB.

This is a diagnostic GRD amplitude-change proxy:
- it is not calibrated RTC backscatter;
- it is not used in the main priority score.

## 8. Explainable planning-priority index

Nominal weights:

H = 0.35T + 0.20B + 0.15V + 0.15P + 0.15C

where:
- T: normalized LST
- B: normalized built-up share
- V: normalized low vegetation
- P: log-normalized population exposure
- C: normalized urban-change stress

All normalization is relative to the current Khalifa City analysis polygons.

If an optional component is unavailable, FalconHeat redistributes its weight
across measured components rather than inventing a replacement value.

## 9. Evidence confidence
The dashboard's confidence percentage is evidence completeness, not uncertainty.

It combines:
- source coverage;
- scene cloud metadata;
- WorldPop availability;
- polygon geometry support.

It must not be presented as a statistical confidence interval.

## 10. Scenario Lab
Scenario controls alter assumed LST, NDVI, built-up share and population exposure,
then recompute the same transparent index against the current AOI normalization
ranges.

The result is a sensitivity analysis and not a physical forecast.

## 11. Main limitations
- Landsat LST is surface temperature, not air temperature.
- A one-season comparison does not establish long-term climate trend.
- NDBI can respond to bright dry soil as well as built surfaces.
- WorldCover 2021 is older than the 2026 thermal/vegetation observation.
- WorldPop is a model estimate.
- Relative scores change if the AOI or comparison polygons change.
- Operational planning would require field validation, local vulnerability data,
  official land-use boundaries and a validated heat-health framework.

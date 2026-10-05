# Spectral Indices Reference

This reference follows the hackathon repository structure and documents the indices used or discussed by FalconHeat.

## NDVI — Normalized Difference Vegetation Index
```text
NDVI = (NIR - Red) / (NIR + Red)
```
FalconHeat uses Sentinel-2 B08 (NIR) and B04 (Red). Higher values generally indicate stronger vegetation signal.

## NDBI — Normalized Difference Built-up Index
```text
NDBI = (SWIR - NIR) / (SWIR + NIR)
```
FalconHeat uses Sentinel-2 B11 (SWIR) and B08 (NIR). NDBI is treated as a spectral built-up signal, not a cadastral building-area measurement.

## BUI — Built-up Index
```text
BUI = NDBI - NDVI
```
Included because it is relevant to the official Theme 2 starter workflow. FalconHeat's production priority model uses WorldCover built-up share instead of BUI.

## MNDWI — Modified Normalized Difference Water Index
```text
MNDWI = (Green - SWIR) / (Green + SWIR)
```
Useful for separating open water from urban/bare surfaces.

## Land-surface temperature
FalconHeat reads Landsat Collection 2 Level-2 surface-temperature data, applies product scale/offset metadata and reports degrees Celsius. This is **land-surface temperature, not air temperature**.

## FalconHeat priority model
```text
H = 0.35T + 0.20B + 0.15V + 0.15P + 0.15C
```
- T: relative Landsat LST
- B: ESA WorldCover built-up share
- V: low Sentinel-2 vegetation
- P: WorldPop estimated resident exposure
- C: conservative 2021→2026 change evidence

The score is a relative planning-priority index, not a medical heat-health threshold.

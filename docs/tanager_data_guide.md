# Tanager Data Guide

This file is included to match the required 813 hackathon repository structure.

## FalconHeat use of Tanager / 813 imagery
FalconHeat's validated production indicators currently come from Sentinel-2, Landsat, ESA WorldCover and WorldPop. The dashboard includes an **813 Challenge Imagery Lab** that can inspect an organizer-provided GeoTIFF and report:
- dimensions
- CRS
- bounds
- band count
- pixel size
- an interactive three-band quicklook

FalconHeat does **not** insert unknown Tanager/813 bands into the priority score until wavelength semantics and calibration are confirmed.

## HDF5 / STAC workflow
For Tanager hyperspectral data:
1. Open the relevant Planet STAC collection.
2. Inspect the STAC item metadata and `assets` dictionary.
3. Identify the surface-reflectance HDF5 asset supplied by the item.
4. Read wavelength/band metadata from the item/product metadata.
5. Load only the bands needed for the desired spectral index.
6. Apply product quality masks before interpretation.

Asset keys can vary by product/version, so the code should inspect the live STAC item rather than assume a hard-coded key.

## Attribution
When using organizer-provided or Planet open Tanager imagery, retain the attribution required by the source dataset and the hackathon guidance.

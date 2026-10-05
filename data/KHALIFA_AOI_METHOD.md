# Khalifa City AOI method

FalconHeat no longer treats a rectangular bounding box as Khalifa City.

## Geometry
1. At refresh time, FalconHeat asks OpenStreetMap/Nominatim for a polygon for
   `Khalifa City, Abu Dhabi, United Arab Emirates`.
2. The returned geometry is sanity-checked to ensure it is actually in the
   Khalifa City part of Abu Dhabi.
3. If a usable polygon is unavailable, a conservative Khalifa City study polygon
   is used. The dashboard explicitly reports when that fallback is active.
4. The AOI is divided into 12 square partitions and **clipped to the AOI polygon**.
   EO pixels outside each clipped polygon are excluded from statistics.

## Names
Analysis polygons are labelled `Near <verified locality/sector anchor> · Kxx`.
`Near` is intentional: the polygons are analytical units and are not presented
as official municipal sector boundaries.

## EO measurements
- Sentinel-2 Level-2A: NDVI / NDBI
- Landsat Collection 2 Level-2: land-surface temperature
- ESA WorldCover 2021: built-up share

Every statistic is masked to the clipped analysis polygon, rather than calculated
from the old rectangular 3×3 grid.

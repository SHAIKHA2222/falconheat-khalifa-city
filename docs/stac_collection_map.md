# STAC Collection Map

## FalconHeat production sources

| Dataset | Access / collection | Use |
|---|---|---|
| Sentinel-2 Level-2A | Microsoft Planetary Computer STAC · `sentinel-2-l2a` | NDVI, NDBI, 2021→2026 comparison |
| Landsat Collection 2 Level-2 | Microsoft Planetary Computer STAC · `landsat-c2-l2` | Land-surface temperature |
| ESA WorldCover | Microsoft Planetary Computer STAC · `esa-worldcover` | Built-up class 50 structural baseline |
| Sentinel-1 GRD | Microsoft Planetary Computer STAC · `sentinel-1-grd` | Optional diagnostic only |

Planetary Computer STAC API:
```text
https://planetarycomputer.microsoft.com/api/stac/v1
```

## Planet Tanager open STAC collections relevant to Theme 2

Urban:
```text
https://www.planet.com/data/stac/tanager-core-imagery/urban/collection.json
```

Natural lands:
```text
https://www.planet.com/data/stac/tanager-core-imagery/natural-lands/collection.json
```

## Exact scene IDs used in the published FalconHeat snapshot

### Landsat
```text
LC08_L2SP_160043_20260924_02_T1
```

### Sentinel-2 current
```text
S2C_MSIL2A_20260927T065641_R063_T40RBN_20260927T121710
S2C_MSIL2A_20260927T065641_R063_T40QBM_20260927T121710
S2C_MSIL2A_20260927T065641_R063_T39RZH_20260927T121710
```

### Sentinel-2 historical
```text
S2B_MSIL2A_20210918T065619_R063_T40RBN_20210918T190936
S2B_MSIL2A_20210918T065619_R063_T40QBM_20210918T192645
S2B_MSIL2A_20210918T065619_R063_T39RZH_20210918T183139
```

### ESA WorldCover
```text
ESA_WorldCover_10m_2021_v200_N24E054
```

"""Real Earth-observation data pipeline for FalconHeat.

The pipeline uses only organizer-approved public sources hosted through
Microsoft Planetary Computer:
  * Sentinel-2 Level-2A (Copernicus) -> NDVI / NDBI
  * Landsat Collection 2 Level-2 (USGS) -> land-surface temperature
  * ESA WorldCover 2021 -> built-up land share

Important implementation detail
-------------------------------
Khalifa City can intersect more than one satellite tile. STAC search returns
*items/tiles*, not a ready-made mosaic. The pipeline therefore selects a
single acquisition day whose tile set covers the AOI and combines all tiles
that intersect each analysis cell. This avoids empty/NaN cells at tile edges.

No synthetic values are generated. If the remote EO products cannot be
retrieved safely, the caller receives a clear error instead of silently
falling back to demo data.
"""
from __future__ import annotations

import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Broad search envelope only. It is NOT treated as the Khalifa City boundary.
# The actual analysis geometry is a polygon and every EO statistic is masked to it.
KHALIFA_BBOX = (54.535, 24.385, 54.625, 24.452)  # west, south, east, north

SUMMER_2026 = "2026-07-01/2026-09-30"
WORLDCOVER_YEAR = "2021"
GRID_ROWS = 3
GRID_COLS = 4

# Conservative fallback study polygon assembled around verified Khalifa City
# localities/sectors (Al Forsan, central Khalifa, Sector 12/32/33 and Etihad Plaza).
# At runtime FalconHeat first tries to replace this with an OSM/Nominatim polygon.
KHALIFA_FALLBACK_RING = [
    [54.5415, 24.3940],
    [54.5450, 24.4215],
    [54.5550, 24.4450],
    [54.5890, 24.4510],
    [54.6155, 24.4485],
    [54.6220, 24.4330],
    [54.6140, 24.4080],
    [54.5960, 24.3900],
    [54.5600, 24.3860],
    [54.5415, 24.3940],
]

# Conservative minimum valid samples per cell after masking.
MIN_S2_PIXELS = 100
MIN_LANDSAT_PIXELS = 12
MIN_WORLDCOVER_PIXELS = 100


class EODataError(RuntimeError):
    """Raised when real EO data cannot be produced safely."""


def _imports():
    try:
        import planetary_computer
        import rasterio
        from pystac_client import Client
        from rasterio.errors import WindowError
        from rasterio.features import geometry_mask
        from rasterio.warp import Resampling, reproject, transform_bounds
        from pyproj import Transformer
        from shapely.geometry import box, shape, mapping, Polygon
        from shapely.ops import unary_union, transform as shp_transform
    except ImportError as exc:
        raise EODataError(
            "Real-EO dependencies are missing. Run `pip install -r requirements.txt` "
            "and restart Streamlit."
        ) from exc
    return {
        "planetary_computer": planetary_computer,
        "rasterio": rasterio,
        "Client": Client,
        "WindowError": WindowError,
        "geometry_mask": geometry_mask,
        "Transformer": Transformer,
        "Resampling": Resampling,
        "reproject": reproject,
        "transform_bounds": transform_bounds,
        "box": box,
        "shape": shape,
        "mapping": mapping,
        "Polygon": Polygon,
        "unary_union": unary_union,
        "shp_transform": shp_transform,
    }



def _http_json(url, params, timeout=20):
    query = urlencode(params)
    req = Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "FalconHeat/2.0 (Arab Youth Space Hackathon; educational PoC)",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _valid_khalifa_geom(geom):
    if geom is None or geom.is_empty:
        return False
    west, south, east, north = geom.bounds
    # Guard against an unrelated place with the same name.
    return (
        54.50 <= west <= 54.65
        and 54.54 <= east <= 54.70
        and 24.34 <= south <= 24.46
        and 24.39 <= north <= 24.50
        and geom.area > 0.00015
    )


def _khalifa_boundary(mod):
    """Return the best available Khalifa City polygon and provenance.

    Priority:
    1) user-supplied `data/khalifa_city_boundary.geojson`
    2) OpenStreetMap/Nominatim polygon
    3) curated conservative fallback polygon

    Satellite indicators still come from Sentinel-2, Landsat and WorldCover.
    """
    fallback = mod["Polygon"](KHALIFA_FALLBACK_RING)

    # Exact/user-approved boundary override. This is useful if the hackathon
    # organizers or municipality provide a GeoJSON boundary, or if the team
    # carefully draws one in geojson.io.
    override = Path(__file__).resolve().parents[1] / "data" / "khalifa_city_boundary.geojson"
    if override.exists():
        try:
            payload = json.loads(override.read_text(encoding="utf-8"))
            if payload.get("type") == "FeatureCollection":
                geoms = [
                    mod["shape"](f["geometry"])
                    for f in payload.get("features", [])
                    if f.get("geometry")
                ]
                geom = mod["unary_union"](geoms) if geoms else None
            elif payload.get("type") == "Feature":
                geom = mod["shape"](payload.get("geometry"))
            else:
                geom = mod["shape"](payload)
            if _valid_khalifa_geom(geom):
                return geom, {
                    "source": "User-supplied Khalifa City GeoJSON",
                    "label": str(override.name),
                    "is_fallback": False,
                }
        except Exception:
            pass
    try:
        data = _http_json(
            "https://nominatim.openstreetmap.org/search",
            {
                "q": "Khalifa City, Abu Dhabi, United Arab Emirates",
                "format": "geojson",
                "polygon_geojson": 1,
                "addressdetails": 1,
                "countrycodes": "ae",
                "limit": 8,
            },
        )
        candidates = []
        for feature in data.get("features", []):
            geom_json = feature.get("geometry")
            if not geom_json or geom_json.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            geom = mod["shape"](geom_json)
            label = str(feature.get("properties", {}).get("display_name", ""))
            if "Khalifa" in label and _valid_khalifa_geom(geom):
                candidates.append((geom.area, geom, label))
        if candidates:
            # Prefer the largest valid Khalifa polygon.
            _, geom, label = max(candidates, key=lambda x: x[0])
            return geom, {
                "source": "OpenStreetMap / Nominatim polygon",
                "label": label,
                "is_fallback": False,
            }
    except Exception:
        pass

    return fallback, {
        "source": "Curated Khalifa City study polygon",
        "label": "Fallback polygon based on verified Khalifa City localities and sector anchors",
        "is_fallback": True,
    }


# Verified local anchors used only as a no-network fallback for human-readable names.
# EO measurements themselves are not derived from these points.
_LOCAL_ANCHORS = [
    ("Al Forsan Village", 24.40405, 54.54889),
    ("Sector 33 · Post Office", 24.40635, 54.56931),
    ("Sector 32 · Community Centre", 24.41648, 54.56609),
    ("Sector 12", 24.42030, 54.57910),
    ("SW12", 24.41872, 54.55005),
    ("SW2", 24.42248, 54.55908),
    ("SE25", 24.41420, 54.59300),
    ("SE36", 24.40747, 54.59957),
    ("SE41", 24.43143, 54.59035),
    ("Etihad Plaza · SE45", 24.44305, 54.60902),
    ("Etihad Airways HQ", 24.44616, 54.61409),
]


def _fallback_local_name(lat, lon):
    def d2(anchor):
        _, alat, alon = anchor
        # longitude adjustment is sufficient at this tiny spatial scale.
        return (lat - alat) ** 2 + ((lon - alon) * 0.91) ** 2
    return min(_LOCAL_ANCHORS, key=d2)[0]


def _reverse_local_name(lat, lon):
    """Use OSM reverse geocoding to get a sector/neighbourhood label."""
    try:
        data = _http_json(
            "https://nominatim.openstreetmap.org/reverse",
            {
                "lat": f"{lat:.7f}",
                "lon": f"{lon:.7f}",
                "format": "jsonv2",
                "zoom": 16,
                "addressdetails": 1,
                "accept-language": "en",
            },
        )
        addr = data.get("address", {}) or {}
        values = [str(v) for v in addr.values()]
        joined = " | ".join(values)

        # Abu Dhabi sector naming appears as Sector 12, SE41, SW2, etc.
        match = re.search(r"\b(?:Sector\s*\d+|SE-?\d+|SW-?\d+)\b", joined, re.I)
        sector = match.group(0).replace("-", "").title() if match else None

        neighbourhood = None
        for key in ("neighbourhood", "quarter", "residential", "suburb"):
            val = addr.get(key)
            if val and str(val).lower() not in {
                "khalifa city", "abu dhabi", "abu dhabi municipality"
            }:
                neighbourhood = str(val)
                break

        road = addr.get("road")
        if sector and neighbourhood and sector.lower() not in neighbourhood.lower():
            return f"{sector} · {neighbourhood}"
        if sector:
            return sector
        if neighbourhood:
            return neighbourhood
        if road:
            return str(road)
    except Exception:
        pass
    return _fallback_local_name(lat, lon)


def _grid_cells(boundary, mod, rows=GRID_ROWS, cols=GRID_COLS):
    """Create clipped analysis polygons that cover Khalifa City, not a rectangle."""
    west, south, east, north = boundary.bounds
    dx = (east - west) / cols
    dy = (north - south) / rows
    raw = []

    for r in range(rows):
        n = north - r * dy
        s = n - dy
        for c in range(cols):
            w = west + c * dx
            e = w + dx
            square = mod["box"](w, s, e, n)
            clipped = square.intersection(boundary)
            if clipped.is_empty:
                continue
            # Ignore only microscopic slivers.
            if clipped.area < square.area * 0.04:
                continue

            # If a MultiPolygon is returned, retain its full geometry.
            p = clipped.representative_point()
            raw.append(
                {
                    "cell_id": f"K{len(raw)+1:02d}",
                    "west": float(clipped.bounds[0]),
                    "south": float(clipped.bounds[1]),
                    "east": float(clipped.bounds[2]),
                    "north": float(clipped.bounds[3]),
                    "longitude": float(p.x),
                    "latitude": float(p.y),
                    "geometry_geojson": json.dumps(mod["mapping"](clipped), separators=(",", ":")),
                    "cell_clip_fraction": float(clipped.area / square.area),
                }
            )

    # Use verified Khalifa City locality anchors for concise map labels.
    # "Near" is deliberate: these are analysis polygons, not claimed official
    # municipal sector boundaries.
    for cell in raw:
        anchor = _fallback_local_name(cell["latitude"], cell["longitude"])
        cell["local_name"] = f"Near {anchor}"
        cell["zone"] = f"Khalifa City · {cell['local_name']} · {cell['cell_id']}"

    return raw


def _open_catalog(mod):
    try:
        return mod["Client"].open(
            PC_STAC, modifier=mod["planetary_computer"].sign_inplace
        )
    except Exception as exc:
        raise EODataError(
            "Could not connect to Microsoft Planetary Computer. Check internet "
            "access and try Refresh EO data again."
        ) from exc


def _datetime(item):
    dt = getattr(item, "datetime", None)
    if dt is not None:
        return dt
    value = item.properties.get("datetime") or item.properties.get("start_datetime")
    if value:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _cloud(item):
    value = item.properties.get("eo:cloud_cover")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1000.0


def _item_geometry(item, mod):
    try:
        if getattr(item, "geometry", None):
            return mod["shape"](item.geometry)
        if getattr(item, "bbox", None):
            return mod["box"](*item.bbox)
    except Exception:
        return None
    return None


def _coverage_fraction(items: Iterable, bbox, mod):
    """Fraction of bbox covered by the union of STAC item geometries."""
    aoi = mod["box"](*bbox)
    geoms = []
    for item in items:
        geom = _item_geometry(item, mod)
        if geom is not None and not geom.is_empty and geom.intersects(aoi):
            geoms.append(geom.intersection(aoi))
    if not geoms or aoi.area <= 0:
        return 0.0
    union = mod["unary_union"](geoms)
    return float(union.area / aoi.area)


def _filter_assets(items: Iterable, required_assets: Iterable[str], label: str):
    required_assets = tuple(required_assets)
    candidates = [
        item for item in items if all(key in item.assets for key in required_assets)
    ]
    if not candidates:
        raise EODataError(
            f"No usable {label} scene matched Khalifa City and the selected period."
        )
    return candidates


def _select_covering_day(items: Iterable, required_assets, label: str, bbox, mod):
    """Select one acquisition day whose *tile set* covers the entire Khalifa AOI.

    The previous implementation chose one low-cloud item. That fails when the AOI
    straddles a Sentinel/Landsat tile edge. Here we group items by acquisition day
    and choose a same-day tile mosaic that covers the study area.
    """
    candidates = _filter_assets(items, required_assets, label)
    groups = defaultdict(list)
    for item in candidates:
        groups[_datetime(item).date().isoformat()].append(item)

    scored = []
    for day, group in groups.items():
        coverage = _coverage_fraction(group, bbox, mod)
        clouds = [min(_cloud(i), 100.0) for i in group if _cloud(i) <= 100]
        cloud_score = float(np.mean(clouds)) if clouds else 1000.0
        scored.append((day, group, coverage, cloud_score))

    if not scored:
        raise EODataError(f"No usable {label} acquisition groups were found.")

    # Require practically complete geometric coverage. Among those groups, prefer
    # lower cloud first and the latest acquisition second.
    full = [x for x in scored if x[2] >= 0.995]
    if full:
        full.sort(
            key=lambda x: (
                x[3],
                -datetime.fromisoformat(x[0]).replace(tzinfo=timezone.utc).timestamp(),
            )
        )
        day, group, coverage, _ = full[0]
        return group, day, coverage

    # Do not silently create partial data. Report the best coverage found so the
    # error is actionable instead of surfacing later as unexplained NaNs.
    best = max(scored, key=lambda x: x[2])
    raise EODataError(
        f"{label} search found tiles, but no single acquisition day covered the "
        f"full Khalifa City AOI. Best same-day coverage was {best[2] * 100:.1f}% "
        f"on {best[0]}. Try a wider date range or Refresh EO data."
    )


def _search_sentinel(catalog, mod, bbox):
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=SUMMER_2026,
        query={"eo:cloud_cover": {"lt": 20}},
        max_items=200,
    )
    return _select_covering_day(
        list(search.items()), ("B04", "B08", "B11", "SCL"), "Sentinel-2", bbox, mod
    )


def _search_landsat(catalog, mod, bbox):
    search = catalog.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=SUMMER_2026,
        query={"eo:cloud_cover": {"lt": 30}},
        max_items=200,
    )
    return _select_covering_day(
        list(search.items()),
        ("lwir11", "qa_pixel"),
        "Landsat surface-temperature",
        bbox,
        mod,
    )


def _search_worldcover(catalog, mod, bbox):
    search = catalog.search(
        collections=["esa-worldcover"],
        bbox=bbox,
        datetime=WORLDCOVER_YEAR,
        max_items=50,
    )
    candidates = _filter_assets(list(search.items()), ("map",), "ESA WorldCover 2021")
    coverage = _coverage_fraction(candidates, bbox, mod)
    if coverage < 0.995:
        raise EODataError(
            f"ESA WorldCover tiles cover only {coverage * 100:.1f}% of the Khalifa City AOI."
        )
    return candidates, coverage


def _cell_bbox(cell):
    return (cell["west"], cell["south"], cell["east"], cell["north"])


def _cell_geom(cell, mod):
    return mod["shape"](json.loads(cell["geometry_geojson"]))


def _cell_raster_mask(cell, shape_, transform, crs, mod):
    """Boolean mask of the clipped Khalifa analysis polygon in a raster grid."""
    geom = _cell_geom(cell, mod)
    transformer = mod["Transformer"].from_crs("EPSG:4326", crs, always_xy=True)
    projected = mod["shp_transform"](transformer.transform, geom)
    return mod["geometry_mask"](
        [mod["mapping"](projected)],
        out_shape=shape_,
        transform=transform,
        invert=True,
    )


def _intersecting_items(items: Iterable, bbox, mod):
    aoi = mod["box"](*bbox)
    scored = []
    for item in items:
        geom = _item_geometry(item, mod)
        if geom is None or geom.is_empty or not geom.intersects(aoi):
            continue
        overlap = float(geom.intersection(aoi).area / aoi.area) if aoi.area else 0.0
        if overlap > 0:
            scored.append((overlap, _cloud(item), item))
    scored.sort(key=lambda x: (-x[0], x[1], -_datetime(x[2]).timestamp()))
    return [x[2] for x in scored]


def _read_aoi(asset_href, bbox, mod, resampling=None, reference=None, honor_nodata=True):
    rasterio = mod["rasterio"]
    transform_bounds = mod["transform_bounds"]
    Resampling = mod["Resampling"]
    reproject = mod["reproject"]

    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
        GDAL_HTTP_MULTIRANGE="YES",
        CPL_VSIL_CURL_USE_HEAD="NO",
    )
    with env:
        with rasterio.open(asset_href) as src:
            src_bounds = transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21)
            window = src.window(*src_bounds).round_offsets().round_lengths()
            try:
                window = window.intersection(
                    rasterio.windows.Window(0, 0, src.width, src.height)
                )
            except mod["WindowError"] as exc:
                raise EODataError("Requested AOI does not intersect this raster tile.") from exc

            if window.width <= 0 or window.height <= 0:
                raise EODataError("Requested AOI produced an empty raster window.")

            if reference is None:
                arr = src.read(1, window=window, masked=False)
                transform = src.window_transform(window)
                return arr, transform, src.crs, src.nodata

            dst = np.full(reference["shape"], np.nan, dtype="float32")
            source = src.read(1, window=window, masked=False)
            source_transform = src.window_transform(window)
            nodata = src.nodata
            effective_nodata = nodata if honor_nodata else None
            reproject(
                source=source,
                destination=dst,
                src_transform=source_transform,
                src_crs=src.crs,
                src_nodata=effective_nodata,
                dst_transform=reference["transform"],
                dst_crs=reference["crs"],
                dst_nodata=np.nan,
                resampling=resampling or Resampling.bilinear,
            )
            return dst, reference["transform"], reference["crs"], np.nan


def _band_scale_offset(asset, default_scale=1.0, default_offset=0.0):
    """Read STAC raster scale/offset metadata when available."""
    try:
        meta = asset.extra_fields.get("raster:bands", [{}])[0]
        return float(meta.get("scale", default_scale)), float(
            meta.get("offset", default_offset)
        )
    except Exception:
        return float(default_scale), float(default_offset)


def _scaled_reflectance(raw, asset):
    scale, offset = _band_scale_offset(asset, 1.0, 0.0)
    return raw.astype("float32") * scale + offset


def _sentinel_piece(item, cell, mod):
    bbox = _cell_bbox(cell)
    Resampling = mod["Resampling"]
    nir_raw, transform, crs, nir_nodata = _read_aoi(
        item.assets["B08"].href, bbox, mod
    )
    ref = {"shape": nir_raw.shape, "transform": transform, "crs": crs}
    red_raw, _, _, red_nodata = _read_aoi(
        item.assets["B04"].href, bbox, mod, Resampling.bilinear, ref
    )
    swir_raw, _, _, swir_nodata = _read_aoi(
        item.assets["B11"].href, bbox, mod, Resampling.bilinear, ref
    )
    scl, _, _, _ = _read_aoi(
        item.assets["SCL"].href, bbox, mod, Resampling.nearest, ref
    )

    nir = _scaled_reflectance(nir_raw, item.assets["B08"])
    red = _scaled_reflectance(red_raw, item.assets["B04"])
    swir = _scaled_reflectance(swir_raw, item.assets["B11"])

    # SCL: reject no-data/saturated/cloud-shadow/cloud/cirrus/snow. Keep
    # vegetation, bare/urban, water and unclassified land pixels.
    invalid_scl = np.isin(np.nan_to_num(scl, nan=0).astype("int16"), [0, 1, 3, 8, 9, 10, 11])
    spatial = _cell_raster_mask(cell, nir_raw.shape, transform, crs, mod)
    valid = spatial & (~invalid_scl) & np.isfinite(nir) & np.isfinite(red) & np.isfinite(swir)

    if nir_nodata is not None:
        valid &= nir_raw != nir_nodata
    if red_nodata is not None and np.isfinite(red_nodata):
        valid &= np.nan_to_num(red_raw, nan=red_nodata) != red_nodata
    if swir_nodata is not None and np.isfinite(swir_nodata):
        valid &= np.nan_to_num(swir_raw, nan=swir_nodata) != swir_nodata

    # Zero raw DNs are no-data for Sentinel-2 COGs in practice.
    valid &= (np.nan_to_num(nir_raw) > 0) & (np.nan_to_num(red_raw) > 0) & (np.nan_to_num(swir_raw) > 0)

    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
        ndbi = (swir - nir) / (swir + nir)

    valid &= np.isfinite(ndvi) & np.isfinite(ndbi)
    valid &= (ndvi >= -1.0) & (ndvi <= 1.0) & (ndbi >= -1.0) & (ndbi <= 1.0)
    return ndvi[valid].astype("float32"), ndbi[valid].astype("float32")


def _sentinel_stats(items, cells, mod):
    ndvi_out, ndbi_out = [], []
    for cell in cells:
        bbox = _cell_bbox(cell)
        ndvi_parts, ndbi_parts = [], []
        for item in _intersecting_items(items, bbox, mod):
            try:
                a, b = _sentinel_piece(item, cell, mod)
            except Exception:
                continue
            if a.size:
                ndvi_parts.append(a)
                ndbi_parts.append(b)

        if ndvi_parts:
            ndvi_vals = np.concatenate(ndvi_parts)
            ndbi_vals = np.concatenate(ndbi_parts)
        else:
            ndvi_vals = np.array([], dtype="float32")
            ndbi_vals = np.array([], dtype="float32")

        if ndvi_vals.size < MIN_S2_PIXELS:
            ndvi_out.append(np.nan)
            ndbi_out.append(np.nan)
        else:
            ndvi_out.append(float(np.nanmedian(ndvi_vals)))
            ndbi_out.append(float(np.nanmedian(ndbi_vals)))
    return ndvi_out, ndbi_out


def _landsat_piece(item, cell, mod):
    bbox = _cell_bbox(cell)
    temp_dn, transform, crs, nodata = _read_aoi(
        item.assets["lwir11"].href, bbox, mod
    )
    ref = {"shape": temp_dn.shape, "transform": transform, "crs": crs}
    qa, _, _, _ = _read_aoi(
        item.assets["qa_pixel"].href,
        bbox,
        mod,
        mod["Resampling"].nearest,
        ref,
        honor_nodata=False,
    )

    scale, offset = _band_scale_offset(item.assets["lwir11"], 0.00341802, 149.0)
    temp_k = temp_dn.astype("float32") * scale + offset
    temp_c = temp_k - 273.15

    qa = np.nan_to_num(qa, nan=1).astype("uint16")
    invalid = np.zeros(qa.shape, dtype=bool)
    # QA_PIXEL bits 0-5: fill, dilated cloud, cirrus, cloud, cloud shadow, snow.
    for bit in (0, 1, 2, 3, 4, 5):
        invalid |= (qa & (1 << bit)) != 0

    spatial = _cell_raster_mask(cell, temp_dn.shape, transform, crs, mod)
    valid = spatial & (~invalid) & np.isfinite(temp_c)
    if nodata is not None:
        valid &= temp_dn != nodata
    valid &= (temp_c > -20) & (temp_c < 80)
    return temp_c[valid].astype("float32")


def _landsat_stats(items, cells, mod):
    out = []
    for cell in cells:
        bbox = _cell_bbox(cell)
        pieces = []
        for item in _intersecting_items(items, bbox, mod):
            try:
                vals = _landsat_piece(item, cell, mod)
            except Exception:
                continue
            if vals.size:
                pieces.append(vals)
        vals = np.concatenate(pieces) if pieces else np.array([], dtype="float32")
        out.append(
            float(np.nanmedian(vals)) if vals.size >= MIN_LANDSAT_PIXELS else np.nan
        )
    return out


def _worldcover_piece(item, cell, mod):
    bbox = _cell_bbox(cell)
    wc, transform, crs, nodata = _read_aoi(item.assets["map"].href, bbox, mod)
    spatial = _cell_raster_mask(cell, wc.shape, transform, crs, mod)
    finite = np.isfinite(wc)
    wc = np.nan_to_num(wc, nan=0).astype("int16")
    valid = spatial & finite & (wc != 0)
    if nodata is not None:
        valid &= wc != nodata
    return int(((wc == 50) & valid).sum()), int(valid.sum())


def _worldcover_stats(items, cells, mod):
    out = []
    for cell in cells:
        bbox = _cell_bbox(cell)
        built_count = 0
        valid_count = 0
        for item in _intersecting_items(items, bbox, mod):
            try:
                b, v = _worldcover_piece(item, cell, mod)
            except Exception:
                continue
            built_count += b
            valid_count += v
        out.append(
            float(built_count / valid_count)
            if valid_count >= MIN_WORLDCOVER_PIXELS
            else np.nan
        )
    return out


def _summary_item_id(items):
    ids = list(dict.fromkeys(item.id for item in items))
    if len(ids) <= 3:
        return " | ".join(ids)
    return f"{ids[0]} (+{len(ids) - 1} additional tiles)"


def _mean_cloud(items):
    vals = [_cloud(i) for i in items if _cloud(i) <= 100]
    return None if not vals else round(float(np.mean(vals)), 2)


def build_khalifa_dataset(
    output_csv: str | Path | None = None,
    metadata_json: str | Path | None = None,
):
    """Fetch and aggregate real EO measurements for clipped Khalifa City analysis polygons.

    Returns (dataframe, metadata). Values are observed/derived from the selected
    public EO products; the FalconHeat relative risk index is computed separately.
    """
    mod = _imports()
    catalog = _open_catalog(mod)
    boundary, boundary_info = _khalifa_boundary(mod)
    aoi_bbox = tuple(float(x) for x in boundary.bounds)
    cells = _grid_cells(boundary, mod)

    try:
        s2_items, s2_day, s2_coverage = _search_sentinel(catalog, mod, aoi_bbox)
        landsat_items, landsat_day, ls_coverage = _search_landsat(catalog, mod, aoi_bbox)
        wc_items, wc_coverage = _search_worldcover(catalog, mod, aoi_bbox)

        ndvi, ndbi = _sentinel_stats(s2_items, cells, mod)
        lst_c = _landsat_stats(landsat_items, cells, mod)
        built_up = _worldcover_stats(wc_items, cells, mod)
    except EODataError:
        raise
    except Exception as exc:
        raise EODataError(f"Earth-observation processing failed: {exc}") from exc

    df = pd.DataFrame(cells)
    df["lst_c"] = np.round(lst_c, 2)
    df["ndvi"] = np.round(ndvi, 4)
    df["ndbi"] = np.round(ndbi, 4)
    df["built_up"] = np.round(built_up, 4)

    if df[["lst_c", "ndvi", "built_up"]].isna().any().any():
        bad_rows = df.loc[
            df[["lst_c", "ndvi", "built_up"]].isna().any(axis=1),
            ["zone", "lst_c", "ndvi", "built_up"],
        ]
        details = "; ".join(
            f"{r.zone} (LST={r.lst_c}, NDVI={r.ndvi}, built={r.built_up})"
            for r in bad_rows.itertuples()
        )
        raise EODataError(
            "Insufficient valid EO pixels after same-day tile mosaicking: " + details
        )

    metadata = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "study_area": "Khalifa City, Abu Dhabi, UAE",
        "aoi_bbox_wgs84": list(aoi_bbox),
        "aoi_boundary_source": boundary_info["source"],
        "aoi_boundary_label": boundary_info["label"],
        "aoi_boundary_is_fallback": boundary_info["is_fallback"],
        "aoi_boundary_geojson": mod["mapping"](boundary),
        "analysis_cells": len(cells),
        "analysis_period": "Summer 2026 (2026-07-01 to 2026-09-30)",
        "sentinel2": {
            "provider": "Copernicus Sentinel-2 Level-2A via Microsoft Planetary Computer",
            "collection": "sentinel-2-l2a",
            "item_id": _summary_item_id(s2_items),
            "item_ids": [i.id for i in s2_items],
            "acquisition": s2_day,
            "scene_cloud_cover_pct": _mean_cloud(s2_items),
            "aoi_coverage_pct": round(s2_coverage * 100, 2),
            "indicator": "Median cloud-masked NDVI per grid cell; NDBI retained as a diagnostic",
            "mosaic_note": "All intersecting Sentinel-2 tiles from one acquisition day are combined per cell.",
        },
        "landsat": {
            "provider": "USGS Landsat Collection 2 Level-2 via Microsoft Planetary Computer",
            "collection": "landsat-c2-l2",
            "item_id": _summary_item_id(landsat_items),
            "item_ids": [i.id for i in landsat_items],
            "acquisition": landsat_day,
            "scene_cloud_cover_pct": _mean_cloud(landsat_items),
            "aoi_coverage_pct": round(ls_coverage * 100, 2),
            "indicator": "Median QA-masked surface temperature (lwir11/ST product) in degrees Celsius",
            "mosaic_note": "All intersecting Landsat tiles from one acquisition day are combined per cell.",
        },
        "worldcover": {
            "provider": "ESA WorldCover 2021 via Microsoft Planetary Computer",
            "collection": "esa-worldcover",
            "item_id": _summary_item_id(wc_items),
            "item_ids": [i.id for i in wc_items],
            "year": 2021,
            "aoi_coverage_pct": round(wc_coverage * 100, 2),
            "indicator": "Fraction of valid pixels classified as Built-up (class 50) per grid cell",
        },
        "risk_note": f"FalconHeat's final 0-100 score is a relative PoC priority index across {len(cells)} clipped Khalifa City analysis polygons, not a validated heat-health threshold.",
    }

    if output_csv is not None:
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv, index=False)
    if metadata_json is not None:
        metadata_json = Path(metadata_json)
        metadata_json.parent.mkdir(parents=True, exist_ok=True)
        metadata_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return df, metadata


def read_cached_dataset(csv_path: str | Path, metadata_path: str | Path):
    csv_path = Path(csv_path)
    metadata_path = Path(metadata_path)
    if not csv_path.exists() or not metadata_path.exists():
        return None, None
    return pd.read_csv(csv_path), json.loads(metadata_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "data" / "processed" / "khalifa_city_eo.csv"
    meta_path = root / "data" / "processed" / "khalifa_city_eo_metadata.json"
    frame, info = build_khalifa_dataset(csv_path, meta_path)
    print(frame.to_string(index=False))
    print("\nSaved:", csv_path)
    print("Metadata:", meta_path)
    print("Sentinel-2:", info["sentinel2"]["item_id"])
    print("Landsat:", info["landsat"]["item_id"])
    print("WorldCover:", info["worldcover"]["item_id"])

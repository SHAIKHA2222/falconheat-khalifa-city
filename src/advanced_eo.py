"""Advanced real-data enrichment for FalconHeat.

Adds:
- Summer-matched Sentinel-2 change indicators (2021 -> 2026)
- WorldPop 2026 polygon population exposure via the official WorldPop API v2
- Optional Sentinel-1 GRD same-track change evidence (diagnostic only)
- Polygon area and transparent evidence-confidence scores

No synthetic values are generated. Optional layers fail gracefully and are marked
unavailable rather than replaced by invented values.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

from . import real_eo as reo

ADVANCED_VERSION = "4.0"
HISTORICAL_SENTINEL_PERIOD = "2021-07-01/2021-09-30"
WORLDPOP_YEAR = 2026
WORLDPOP_API = "https://api.worldpop.org/v2"
SAR_CURRENT_PERIOD = "2026-07-01/2026-09-30"
SAR_HISTORICAL_PERIOD = "2021-07-01/2021-09-30"


def _cells_from_df(df: pd.DataFrame) -> list[dict]:
    return df.to_dict(orient="records")


def _area_km2(geom_json: str | dict) -> float:
    geom = shape(json.loads(geom_json) if isinstance(geom_json, str) else geom_json)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32640", always_xy=True)
    projected = shp_transform(transformer.transform, geom)
    return float(projected.area / 1_000_000.0)


def _search_sentinel_period(catalog, mod, bbox, period: str, label: str):
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=period,
        query={"eo:cloud_cover": {"lt": 20}},
        max_items=250,
    )
    return reo._select_covering_day(
        list(search.items()),
        ("B04", "B08", "B11", "SCL"),
        label,
        bbox,
        mod,
    )


def _historical_sentinel(df: pd.DataFrame, metadata: dict):
    mod = reo._imports()
    catalog = reo._open_catalog(mod)
    bbox = tuple(metadata["aoi_bbox_wgs84"])
    items, day, coverage = _search_sentinel_period(
        catalog, mod, bbox, HISTORICAL_SENTINEL_PERIOD, "Historical Sentinel-2"
    )
    cells = _cells_from_df(df)
    ndvi, ndbi = reo._sentinel_stats(items, cells, mod)
    return (
        np.asarray(ndvi, dtype="float64"),
        np.asarray(ndbi, dtype="float64"),
        {
            "provider": "Copernicus Sentinel-2 Level-2A via Microsoft Planetary Computer",
            "collection": "sentinel-2-l2a",
            "period": HISTORICAL_SENTINEL_PERIOD,
            "acquisition": day,
            "scene_cloud_cover_pct": reo._mean_cloud(items),
            "aoi_coverage_pct": round(float(coverage) * 100, 2),
            "item_id": reo._summary_item_id(items),
            "item_ids": [i.id for i in items],
            "indicator": "Summer-matched historical NDVI/NDBI baseline for change analysis",
        },
    )


def _submit_worldpop_tasks(cells: list[dict], year: int = WORLDPOP_YEAR):
    tasks = {}
    errors = {}
    session = requests.Session()
    for cell in cells:
        geom = json.loads(cell["geometry_geojson"])
        payload = {"geojson": geom, "year": year, "resolution": "100m"}
        try:
            response = session.post(
                f"{WORLDPOP_API}/population", json=payload, timeout=45
            )
            response.raise_for_status()
            body = response.json()
            task_id = body.get("task_id")
            if task_id:
                tasks[cell["cell_id"]] = task_id
            else:
                # Future-proof in case the API starts returning synchronous results.
                result = body.get("result") or {}
                total = result.get("total_population")
                if total is not None:
                    tasks[cell["cell_id"]] = {"direct": float(total)}
                else:
                    errors[cell["cell_id"]] = f"No task_id in WorldPop response: {body}"
        except Exception as exc:
            errors[cell["cell_id"]] = str(exc)
        time.sleep(0.12)
    return tasks, errors


def _worldpop_population(cells: list[dict], year: int = WORLDPOP_YEAR):
    """Return estimated population totals per analysis polygon.

    WorldPop API v2 is asynchronous. All tasks are submitted first, then polled
    together to avoid serial multi-minute waits.
    """
    tasks, errors = _submit_worldpop_tasks(cells, year)
    results = {}
    pending = {
        cid: tid for cid, tid in tasks.items() if not isinstance(tid, dict)
    }
    for cid, item in tasks.items():
        if isinstance(item, dict) and "direct" in item:
            results[cid] = item["direct"]

    deadline = time.time() + 180
    session = requests.Session()
    while pending and time.time() < deadline:
        finished = []
        for cid, task_id in list(pending.items()):
            try:
                r = session.get(f"{WORLDPOP_API}/tasks/{task_id}", timeout=30)
                r.raise_for_status()
                body = r.json()
                status = str(body.get("status", "")).lower()
                if status == "success":
                    result = body.get("result") or {}
                    total = (
                        result.get("total_population")
                        if isinstance(result, dict)
                        else None
                    )
                    if total is None and isinstance(result, dict):
                        # Some API versions use a shorter key.
                        total = result.get("population")
                    if total is not None:
                        results[cid] = float(total)
                    else:
                        errors[cid] = f"WorldPop result had no population total: {result}"
                    finished.append(cid)
                elif status in {"failure", "failed", "error"}:
                    errors[cid] = str(body.get("error") or body)
                    finished.append(cid)
            except Exception as exc:
                # Keep polling transient failures until deadline.
                errors[cid] = str(exc)
        for cid in finished:
            pending.pop(cid, None)
        if pending:
            time.sleep(2)

    for cid in pending:
        errors[cid] = "WorldPop task timed out before a result was returned."

    values = [
        results.get(cell["cell_id"], np.nan)
        for cell in cells
    ]
    ok = int(np.isfinite(values).sum())
    return np.asarray(values, dtype="float64"), {
        "provider": "WorldPop Global2 population API v2",
        "year": year,
        "resolution": "100m",
        "endpoint": WORLDPOP_API,
        "successful_cells": ok,
        "total_cells": len(cells),
        "errors": errors,
        "note": (
            "WorldPop population values are model-based gridded estimates, not a census count. "
            "FalconHeat sums the official WorldPop polygon estimate for each analysis polygon."
        ),
    }


def _sar_item_key(item):
    p = item.properties
    return (
        p.get("sat:relative_orbit"),
        p.get("sat:orbit_state"),
        p.get("sar:instrument_mode"),
    )


def _sar_search(catalog, bbox, period):
    search = catalog.search(
        collections=["sentinel-1-grd"],
        bbox=bbox,
        datetime=period,
        max_items=300,
    )
    items = [
        i for i in search.items()
        if "vv" in i.assets
        and str(i.properties.get("sar:instrument_mode", "IW")) == "IW"
    ]
    return items


def _choose_sar_pair(catalog, bbox, mod):
    """Choose 2021/2026 Sentinel-1 GRD groups on the same track when possible."""
    historical = _sar_search(catalog, bbox, SAR_HISTORICAL_PERIOD)
    current = _sar_search(catalog, bbox, SAR_CURRENT_PERIOD)
    if not historical or not current:
        raise reo.EODataError("No suitable Sentinel-1 GRD items were found.")

    by_hist = defaultdict(list)
    by_cur = defaultdict(list)
    for item in historical:
        by_hist[_sar_item_key(item)].append(item)
    for item in current:
        by_cur[_sar_item_key(item)].append(item)

    shared = [k for k in by_hist if k in by_cur and k[0] is not None]
    candidates = []
    for key in shared:
        try:
            h_items, h_day, h_cov = reo._select_covering_day(
                by_hist[key], ("vv",), "Historical Sentinel-1 GRD", bbox, mod
            )
            c_items, c_day, c_cov = reo._select_covering_day(
                by_cur[key], ("vv",), "Current Sentinel-1 GRD", bbox, mod
            )
            candidates.append((key, h_items, h_day, h_cov, c_items, c_day, c_cov))
        except Exception:
            continue
    if not candidates:
        raise reo.EODataError(
            "Sentinel-1 scenes were found, but no matched same-track 2021/2026 pair covered the AOI."
        )
    # Prefer the candidate with highest joint coverage and dates nearest late summer.
    candidates.sort(
        key=lambda x: (
            -(x[3] + x[6]),
            abs(datetime.fromisoformat(x[2]).timetuple().tm_yday - 250)
            + abs(datetime.fromisoformat(x[5]).timetuple().tm_yday - 250),
        )
    )
    return candidates[0]


def _sar_piece(item, cell, mod):
    """Median GRD VV detected-amplitude in dB for a clipped analysis polygon.

    This is a diagnostic same-track change proxy, not calibrated RTC backscatter.
    It is intentionally excluded from the FalconHeat priority score.
    """
    bbox = reo._cell_bbox(cell)
    raw, transform, crs, nodata = reo._read_aoi(item.assets["vv"].href, bbox, mod)
    spatial = reo._cell_raster_mask(cell, raw.shape, transform, crs, mod)
    valid = spatial & np.isfinite(raw)
    if nodata is not None:
        valid &= raw != nodata
    valid &= raw > 0
    vals = raw[valid].astype("float64")
    if vals.size < 100:
        return np.nan
    db = 20.0 * np.log10(vals)
    db = db[np.isfinite(db)]
    return float(np.nanmedian(db)) if db.size else np.nan


def _sar_stats(items, cells, mod):
    out = []
    for cell in cells:
        vals = []
        for item in reo._intersecting_items(items, reo._cell_bbox(cell), mod):
            try:
                v = _sar_piece(item, cell, mod)
            except Exception:
                continue
            if np.isfinite(v):
                vals.append(v)
        out.append(float(np.nanmedian(vals)) if vals else np.nan)
    return np.asarray(out, dtype="float64")


def _sar_change(df: pd.DataFrame, metadata: dict):
    mod = reo._imports()
    catalog = reo._open_catalog(mod)
    bbox = tuple(metadata["aoi_bbox_wgs84"])
    key, h_items, h_day, h_cov, c_items, c_day, c_cov = _choose_sar_pair(
        catalog, bbox, mod
    )
    cells = _cells_from_df(df)
    h = _sar_stats(h_items, cells, mod)
    c = _sar_stats(c_items, cells, mod)
    delta = c - h
    return h, c, delta, {
        "provider": "Copernicus Sentinel-1 GRD via Microsoft Planetary Computer",
        "collection": "sentinel-1-grd",
        "relative_orbit": key[0],
        "orbit_state": key[1],
        "instrument_mode": key[2],
        "historical_acquisition": h_day,
        "current_acquisition": c_day,
        "historical_item_id": reo._summary_item_id(h_items),
        "current_item_id": reo._summary_item_id(c_items),
        "historical_coverage_pct": round(h_cov * 100, 2),
        "current_coverage_pct": round(c_cov * 100, 2),
        "indicator": "Same-track VV detected-amplitude change in dB (diagnostic only)",
        "caution": (
            "This is a same-track GRD amplitude-change diagnostic, not calibrated RTC "
            "backscatter and is excluded from the FalconHeat priority score."
        ),
    }


def _evidence_confidence(df: pd.DataFrame, metadata: dict, population_available: pd.Series):
    """Transparent evidence-completeness score, not statistical uncertainty."""
    s2_cloud = metadata.get("sentinel2", {}).get("scene_cloud_cover_pct")
    h_cloud = metadata.get("sentinel2_historical", {}).get("scene_cloud_cover_pct")
    ls_cloud = metadata.get("landsat", {}).get("scene_cloud_cover_pct")
    s2_cov = metadata.get("sentinel2", {}).get("aoi_coverage_pct", 0) / 100.0
    h_cov = metadata.get("sentinel2_historical", {}).get("aoi_coverage_pct", 0) / 100.0
    ls_cov = metadata.get("landsat", {}).get("aoi_coverage_pct", 0) / 100.0
    wc_cov = metadata.get("worldcover", {}).get("aoi_coverage_pct", 0) / 100.0

    def cloud_quality(x):
        return 0.7 if x is None else max(0.0, min(1.0, 1.0 - float(x) / 35.0))

    scene_quality = (
        0.22 * cloud_quality(s2_cloud) * s2_cov
        + 0.16 * cloud_quality(h_cloud) * h_cov
        + 0.22 * cloud_quality(ls_cloud) * ls_cov
        + 0.15 * wc_cov
    )
    pop = population_available.astype(float) * 0.15
    geom = np.clip(df.get("cell_clip_fraction", 1.0).astype(float), 0.25, 1.0) * 0.10
    return np.clip(100.0 * (scene_quality + pop + geom), 0, 100)


def enrich_advanced_dataset(df: pd.DataFrame, metadata: dict):
    """Add temporal change, exposure, optional SAR evidence, and confidence."""
    out = df.copy()
    cells = _cells_from_df(out)

    # 1) Summer-matched historical Sentinel-2 baseline.
    try:
        ndvi_2021, ndbi_2021, hist_meta = _historical_sentinel(out, metadata)
        out["ndvi_2021"] = np.round(ndvi_2021, 4)
        out["ndbi_2021"] = np.round(ndbi_2021, 4)
        out["ndvi_change"] = np.round(out["ndvi"] - out["ndvi_2021"], 4)
        out["ndbi_change"] = np.round(out["ndbi"] - out["ndbi_2021"], 4)
        metadata["sentinel2_historical"] = hist_meta
    except Exception as exc:
        out["ndvi_2021"] = np.nan
        out["ndbi_2021"] = np.nan
        out["ndvi_change"] = np.nan
        out["ndbi_change"] = np.nan
        metadata["sentinel2_historical"] = {
            "status": "unavailable",
            "error": str(exc),
            "period": HISTORICAL_SENTINEL_PERIOD,
        }

    # 2) WorldPop 2026 exposure.
    try:
        population, pop_meta = _worldpop_population(cells, WORLDPOP_YEAR)
        out["population_2026"] = np.round(population, 1)
        metadata["worldpop"] = pop_meta
    except Exception as exc:
        out["population_2026"] = np.nan
        metadata["worldpop"] = {
            "status": "unavailable",
            "year": WORLDPOP_YEAR,
            "error": str(exc),
        }

    # Polygon area & density.
    out["area_km2"] = [
        round(_area_km2(g), 4) for g in out["geometry_geojson"]
    ]
    with np.errstate(divide="ignore", invalid="ignore"):
        out["population_density_km2"] = np.where(
            out["area_km2"] > 0,
            out["population_2026"] / out["area_km2"],
            np.nan,
        )
    out["population_density_km2"] = np.round(out["population_density_km2"], 1)

    # 3) Optional Sentinel-1 change evidence. Never blocks the dashboard.
    try:
        sar_h, sar_c, sar_d, sar_meta = _sar_change(out, metadata)
        out["sar_vv_2021_db"] = np.round(sar_h, 3)
        out["sar_vv_2026_db"] = np.round(sar_c, 3)
        out["sar_vv_change_db"] = np.round(sar_d, 3)
        metadata["sentinel1"] = sar_meta
    except Exception as exc:
        out["sar_vv_2021_db"] = np.nan
        out["sar_vv_2026_db"] = np.nan
        out["sar_vv_change_db"] = np.nan
        metadata["sentinel1"] = {
            "status": "unavailable",
            "error": str(exc),
            "caution": (
                "SAR evidence is optional and is not replaced with synthetic values."
            ),
        }

    # 4) Evidence completeness.
    out["data_confidence"] = np.round(
        _evidence_confidence(
            out,
            metadata,
            out["population_2026"].notna(),
        ),
        1,
    )

    metadata["advanced_version"] = ADVANCED_VERSION
    metadata["advanced_features"] = {
        "historical_sentinel": bool(out["ndvi_2021"].notna().any()),
        "worldpop_2026": bool(out["population_2026"].notna().any()),
        "sentinel1_diagnostic": bool(out["sar_vv_change_db"].notna().any()),
        "confidence_definition": (
            "Evidence-completeness score combining source coverage, scene cloud metadata, "
            "population availability and polygon geometry. It is not a statistical confidence interval."
        ),
    }
    return out, metadata

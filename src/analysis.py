"""Transparent FalconHeat priority model.

The model is deliberately an interpretable planning-priority index, not a
medical heat-risk model. It combines observed/derived EO indicators and
WorldPop exposure when available.

Default component weights:
- 35% current Landsat land-surface temperature
- 20% WorldCover built-up share
- 15% low Sentinel-2 vegetation (NDVI)
- 15% WorldPop population exposure
- 15% 2021->2026 urban-change stress (vegetation loss + NDBI increase)

If an optional source is unavailable, its weight is redistributed across the
available components for that cell. No synthetic replacement values are used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LEVEL_ORDER = ["Low", "Moderate", "High", "Very High"]

BASE_WEIGHTS = {
    "temperature": 0.35,
    "built_up": 0.20,
    "low_vegetation": 0.15,
    "population": 0.15,
    "urban_change": 0.15,
}

# Conservative PoC tolerance band for single-season spectral-index change.
# Changes inside +/-0.02 are treated as inconclusive rather than amplified by
# relative min-max normalization. These are transparency thresholds, not
# universal remote-sensing significance thresholds.
NDVI_CHANGE_TOLERANCE = 0.02
NDBI_CHANGE_TOLERANCE = 0.02
CHANGE_SCALE = 0.08


def normalize(s):
    """Min-max normalization within the current study polygons."""
    s = pd.to_numeric(s, errors="coerce")
    finite = s[np.isfinite(s)]
    if finite.empty:
        return pd.Series(np.nan, index=s.index, dtype=float)
    lo, hi = float(finite.min()), float(finite.max())
    span = hi - lo
    if span == 0:
        out = pd.Series(0.5, index=s.index, dtype=float)
        out[s.isna()] = np.nan
        return out
    return (s - lo) / span



def normalize_positive_stress(s):
    """Normalize a non-negative stress signal; all-zero means zero stress."""
    s = pd.to_numeric(s, errors="coerce").clip(lower=0)
    finite = s[np.isfinite(s)]
    if finite.empty:
        return pd.Series(np.nan, index=s.index, dtype=float)
    hi = float(finite.max())
    lo = float(finite.min())
    if hi <= 0:
        out = pd.Series(0.0, index=s.index, dtype=float)
        out[s.isna()] = np.nan
        return out
    if hi == lo:
        out = pd.Series(0.5, index=s.index, dtype=float)
        out[s.isna()] = np.nan
        return out
    return (s - lo) / (hi - lo)

def classify(score):
    if score < 25:
        return "Low"
    if score < 50:
        return "Moderate"
    if score < 75:
        return "High"
    return "Very High"


def _recommendation(r):
    actions = []
    # Focus on the largest explainable drivers.
    drivers = {
        "temperature": float(r.get("contrib_temperature", 0)),
        "built": float(r.get("contrib_built_up", 0)),
        "vegetation": float(r.get("contrib_low_vegetation", 0)),
        "population": float(r.get("contrib_population", 0)),
        "change": float(r.get("contrib_urban_change", 0)),
    }
    ranked = sorted(drivers, key=drivers.get, reverse=True)
    for driver in ranked[:3]:
        if driver == "temperature" and drivers[driver] > 4:
            actions.append(
                "Prioritize shade, cool roofs/pavements and on-site thermal validation"
            )
        elif driver == "built" and drivers[driver] > 3:
            actions.append(
                "Reduce exposed impervious surfaces and add shaded pedestrian links"
            )
        elif driver == "vegetation" and drivers[driver] > 2:
            actions.append(
                "Increase climate-resilient tree canopy and connect green corridors"
            )
        elif driver == "population" and drivers[driver] > 2:
            actions.append(
                "Prioritize cooling around homes, schools, transit and high-footfall public space"
            )
        elif driver == "change" and drivers[driver] > 2:
            actions.append(
                "Review recent development/vegetation-loss hotspots before further land conversion"
            )

    if not actions:
        actions.append("Preserve existing vegetation and continue seasonal monitoring")
    return ". ".join(dict.fromkeys(actions)) + "."


def run_analysis(data):
    """Analyze real EO/exposure indicators and produce an explainable priority index."""
    df = pd.read_csv(data) if not isinstance(data, pd.DataFrame) else data.copy()
    required = {"zone", "latitude", "longitude", "lst_c", "ndvi", "built_up"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))

    for col in ["latitude", "longitude", "lst_c", "ndvi", "built_up"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if df[["latitude", "longitude", "lst_c", "ndvi", "built_up"]].isna().any().any():
        raise ValueError("Core EO indicators contain missing values.")

    # Current-state drivers.
    df["temp_norm"] = normalize(df["lst_c"])
    df["built_norm"] = normalize(df["built_up"])
    df["low_veg_norm"] = 1.0 - normalize(df["ndvi"])

    # Population: log transform avoids one dense polygon dominating the entire index.
    if "population_2026" in df.columns:
        pop = pd.to_numeric(df["population_2026"], errors="coerce")
        df["population_norm"] = normalize(np.log1p(pop.clip(lower=0)))
    else:
        df["population_norm"] = np.nan

    # Conservative recent-change evidence.
    # A single 2021-vs-2026 seasonal comparison can contain small residual
    # differences from atmosphere, acquisition geometry and surface condition.
    # Do not amplify tiny changes into a full 15-point contribution.
    if {"ndvi_change", "ndbi_change"}.issubset(df.columns):
        ndvi_change = pd.to_numeric(df["ndvi_change"], errors="coerce")
        ndbi_change = pd.to_numeric(df["ndbi_change"], errors="coerce")

        # Keep raw descriptive changes.
        df["vegetation_loss"] = (-ndvi_change).clip(lower=0)
        df["ndbi_gain"] = ndbi_change.clip(lower=0)

        # Only the amount exceeding the transparent tolerance contributes.
        veg_excess = ((-ndvi_change) - NDVI_CHANGE_TOLERANCE).clip(lower=0)
        ndbi_excess = (ndbi_change - NDBI_CHANGE_TOLERANCE).clip(lower=0)

        veg_stress = (veg_excess / CHANGE_SCALE).clip(0, 1)
        ndbi_stress = (ndbi_excess / CHANGE_SCALE).clip(0, 1)

        # Either vegetation loss or positive NDBI change can provide evidence,
        # but each contributes at most half of the change component.
        df["urban_change_norm"] = (0.5 * veg_stress + 0.5 * ndbi_stress).clip(0, 1)
        missing_change = ndvi_change.isna() | ndbi_change.isna()
        df.loc[missing_change, "urban_change_norm"] = np.nan
        df["clear_change_flag"] = (
            (ndvi_change <= -NDVI_CHANGE_TOLERANCE)
            | (ndbi_change >= NDBI_CHANGE_TOLERANCE)
        ) & (~missing_change)
    else:
        df["vegetation_loss"] = np.nan
        df["ndbi_gain"] = np.nan
        df["urban_change_norm"] = np.nan
        df["clear_change_flag"] = False

    # Row-specific weighted sum. Missing optional sources are not imputed.
    mapping = {
        "temperature": "temp_norm",
        "built_up": "built_norm",
        "low_vegetation": "low_veg_norm",
        "population": "population_norm",
        "urban_change": "urban_change_norm",
    }
    contribution_cols = []
    scores = []
    effective_weights = []

    # Initialize contribution columns.
    for key in mapping:
        col = f"contrib_{key}"
        df[col] = 0.0
        contribution_cols.append(col)

    for idx, row in df.iterrows():
        available = {
            key: BASE_WEIGHTS[key]
            for key, col in mapping.items()
            if pd.notna(row[col])
        }
        total_w = sum(available.values())
        weights = {key: w / total_w for key, w in available.items()} if total_w else {}
        score = 0.0
        for key, col in mapping.items():
            if key in weights:
                points = 100.0 * weights[key] * float(row[col])
                df.at[idx, f"contrib_{key}"] = points
                score += points
        scores.append(score)
        effective_weights.append(
            "; ".join(f"{k}:{weights[k]:.3f}" for k in weights)
        )

    df["risk_score"] = np.round(np.clip(scores, 0, 100), 1)
    df["risk_level"] = df["risk_score"].apply(classify)
    df["effective_weights"] = effective_weights

    # Intuitive context metrics.
    median_lst = float(df["lst_c"].median())
    df["surface_heat_anomaly_c"] = np.round(df["lst_c"] - median_lst, 2)
    df["recommendation"] = df.apply(_recommendation, axis=1)

    # Explainability: top driver per polygon.
    driver_labels = {
        "contrib_temperature": "Surface temperature",
        "contrib_built_up": "Built-up land",
        "contrib_low_vegetation": "Low vegetation",
        "contrib_population": "Population exposure",
        "contrib_urban_change": "Recent change evidence",
    }
    df["top_driver"] = df[contribution_cols].idxmax(axis=1).map(driver_labels)

    return df.sort_values("risk_score", ascending=False).reset_index(drop=True)


def scenario_score(
    df: pd.DataFrame,
    row_index: int,
    lst_delta_c: float = 0.0,
    ndvi_delta: float = 0.0,
    built_delta: float = 0.0,
    exposure_reduction_pct: float = 0.0,
):
    """Recalculate one cell under user-defined illustrative intervention assumptions.

    This is a scenario calculation, not a physical forecast.
    """
    baseline = df.copy()
    row = baseline.loc[row_index].copy()

    # Use the current AOI normalization ranges so the before/after comparison is stable.
    def norm_value(value, series):
        finite = pd.to_numeric(series, errors="coerce").dropna()
        if finite.empty:
            return np.nan
        lo, hi = float(finite.min()), float(finite.max())
        if hi == lo:
            return 0.5
        return float(np.clip((value - lo) / (hi - lo), 0, 1))

    temp = max(-20.0, float(row["lst_c"]) + float(lst_delta_c))
    ndvi = float(np.clip(float(row["ndvi"]) + float(ndvi_delta), -1, 1))
    built = float(np.clip(float(row["built_up"]) + float(built_delta), 0, 1))

    components = {
        "temperature": norm_value(temp, baseline["lst_c"]),
        "built_up": norm_value(built, baseline["built_up"]),
        "low_vegetation": 1.0 - norm_value(ndvi, baseline["ndvi"]),
    }

    if pd.notna(row.get("population_2026", np.nan)):
        pop_new = float(row["population_2026"]) * (1.0 - exposure_reduction_pct / 100.0)
        log_series = np.log1p(pd.to_numeric(baseline["population_2026"], errors="coerce").clip(lower=0))
        components["population"] = norm_value(np.log1p(max(0, pop_new)), log_series)
    else:
        components["population"] = np.nan

    components["urban_change"] = row.get("urban_change_norm", np.nan)

    available = {
        k: BASE_WEIGHTS[k] for k, value in components.items() if pd.notna(value)
    }
    total_w = sum(available.values())
    weights = {k: w / total_w for k, w in available.items()}
    contrib = {
        k: 100 * weights[k] * float(components[k])
        for k in weights
    }
    score = float(sum(contrib.values()))
    return {
        "score": round(score, 1),
        "level": classify(score),
        "lst_c": round(temp, 2),
        "ndvi": round(ndvi, 4),
        "built_up": round(built, 4),
        "contributions": contrib,
        "note": "Illustrative scenario only; slider changes are user assumptions, not forecast model outputs.",
    }

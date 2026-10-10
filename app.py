from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile

import numpy as np
import pandas as pd
import streamlit as st
import folium
from folium.plugins import Fullscreen, MiniMap
from streamlit_folium import st_folium
import plotly.graph_objects as go

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from src.analysis import run_analysis, scenario_score, BASE_WEIGHTS
from src.real_eo import (
    EODataError,
    build_khalifa_dataset,
    read_cached_dataset,
)
from src.advanced_eo import enrich_advanced_dataset, ADVANCED_VERSION

st.set_page_config(
    page_title="FalconHeat AI | Khalifa City Urban Heat Intelligence",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_DIR = BASE / "data" / "processed"
CACHE_CSV = CACHE_DIR / "khalifa_city_eo.csv"
CACHE_META = CACHE_DIR / "khalifa_city_eo_metadata.json"
PUBLIC_SNAPSHOT = (CACHE_DIR / "deployment_snapshot.marker").exists()

# ------------------------------ STYLE ---------------------------------------
st.markdown(
    """
<style>
:root{
  --bg:#061713;--panel:#0b241e;--panel2:#0f2d26;--line:#21453b;
  --text:#eef7f4;--muted:#93aaa3;--green:#38d39f;--amber:#f4c95d;
  --orange:#ff8c42;--red:#ff5353;--cyan:#77d6e6;
}
.stApp{background:var(--bg);color:var(--text)}
.block-container{padding-top:1.4rem;max-width:1500px}
[data-testid="stSidebar"]{background:#08231d;border-right:1px solid #173a31}
h1,h2,h3{letter-spacing:-.02em}
.hero{padding:28px 30px;border:1px solid var(--line);border-radius:22px;
background:linear-gradient(125deg,#0c2a22 0%,#0b1e1a 55%,#142219 100%);margin-bottom:18px}
.eyebrow{font-size:.78rem;letter-spacing:.16em;text-transform:uppercase;color:#75b8a5;font-weight:800}
.hero-title{font-size:3.15rem;font-weight:900;line-height:1;margin:7px 0 9px}
.hero-sub{font-size:1.08rem;color:#bed0ca;max-width:1050px;line-height:1.55}
.badge{display:inline-block;border:1px solid #2b6354;background:#0f352c;color:#94e8cc;
padding:7px 11px;border-radius:999px;font-size:.76rem;font-weight:800;margin-top:16px}
.section-label{font-size:.76rem;text-transform:uppercase;letter-spacing:.14em;color:#6da998;font-weight:800;margin-top:12px}
.section-title{font-size:2rem;font-weight:900;margin:2px 0 14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:17px 18px;height:100%}
.card strong{color:white}
.muted{color:var(--muted)}
.rank{background:#0b261f;border:1px solid #1f4b3f;border-radius:17px;padding:14px 16px;margin:0 0 10px}
.rank-name{font-weight:850;color:white;font-size:1rem}
.rank-meta{font-size:.86rem;color:#a7bbb5;margin-top:5px}
.source-note{background:#0b241e;border-left:4px solid #43c79a;border-radius:12px;padding:15px 17px;color:#b9ccc6}
.warn-note{background:#2b2511;border-left:4px solid #e8bc49;border-radius:12px;padding:15px 17px;color:#e6d8ae}
.action{background:#102c25;border:1px solid #235345;border-radius:15px;padding:16px;color:#d4e6e0}
.smallcaps{font-size:.74rem;text-transform:uppercase;letter-spacing:.12em;color:#7ea79b;font-weight:800}
.metric-mini{font-size:1.65rem;font-weight:900;color:white;margin:4px 0}
.source-date{font-size:1.42rem;font-weight:900;color:white;margin:5px 0;white-space:nowrap}
.formula-card{background:#0b2a23;border:1px solid #235044;border-radius:15px;padding:13px 14px;margin:8px 0 10px}
.formula{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:.91rem;font-weight:800;line-height:1.55;color:#effaf6;white-space:normal;overflow-wrap:anywhere}
.formula-key{font-size:.80rem;color:#aac1ba;line-height:1.65;margin-top:8px}
.kpi-card{background:#0b241e;border:1px solid #1b4238;border-radius:17px;padding:16px 17px;min-height:126px}
.kpi-label{font-size:.77rem;text-transform:uppercase;letter-spacing:.08em;color:#89a89f;font-weight:800}
.kpi-value{font-size:2rem;line-height:1.05;font-weight:900;color:#f4fbf8;margin:8px 0 6px;white-space:normal;overflow-wrap:anywhere}
.kpi-sub{font-size:.82rem;color:#9db6ae;line-height:1.35}
.insight{background:linear-gradient(110deg,#0d3027,#11271f);border:1px solid #2d5a4d;border-radius:17px;padding:17px 19px;color:#d9e9e4;line-height:1.55}
.insight b{color:white}
.rank-insight{font-size:.78rem;color:#89a99f;line-height:1.4;margin-top:7px}
[data-testid="stMetric"]{background:#0b241e;border:1px solid #1b4238;padding:14px;border-radius:16px}
[data-testid="stMetricValue"]{font-size:clamp(1.55rem,2.15vw,2.3rem);white-space:normal;overflow:visible;text-overflow:clip}
[data-testid="stMetricDelta"]{white-space:normal;overflow:visible;text-overflow:clip}
div[data-testid="stTabs"] button{font-weight:800}
@media(max-width:640px){.hero{padding:18px}.hero-title{font-size:2.2rem}.source-date{white-space:normal;overflow-wrap:anywhere}.section-title{font-size:1.5rem}}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------ DATA ----------------------------------------
if "eo_refresh_nonce" not in st.session_state:
    st.session_state.eo_refresh_nonce = 0

with st.sidebar:
    st.markdown("## ◈ FalconHeat")
    st.caption("KHALIFA CITY · ADVANCED REAL EO")
    if PUBLIC_SNAPSHOT:
        st.success("● Published competition snapshot")
        st.caption("Real EO snapshot · September 2026 · interactive filters and Scenario Lab remain enabled.")
    elif st.button(
        "↻ Refresh all EO data",
        use_container_width=True,
        help="Re-query Sentinel-2, Landsat, WorldCover, WorldPop and optional Sentinel-1 evidence.",
    ):
        st.session_state.eo_refresh_nonce += 1
        st.cache_data.clear()

    st.divider()
    st.markdown("#### Explainable priority model")
    st.markdown(
        """
        <div class="formula-card">
          <div class="formula">H = 100 × (0.35T + 0.20B + 0.15V + 0.15P + 0.15C)</div>
          <div class="formula-key">
            <b>T</b> surface heat · <b>B</b> built-up land · <b>V</b> low vegetation<br>
            <b>P</b> estimated population exposure · <b>C</b> conservative 2021→2026 change evidence
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Missing optional real-data components are reweighted across available measured inputs. No synthetic values are inserted."
    )

    if PUBLIC_SNAPSHOT:
        with st.expander("Study boundary"):
            st.caption(
                "This analysis covers a defined study area in Khalifa City, Abu Dhabi. "
                "It does not represent an official municipal boundary."
            )
    else:
        with st.expander("Study boundary"):
            st.caption(
                "Optional: upload an organizer/municipal Khalifa City GeoJSON. "
                "It overrides the automatic OSM/fallback study boundary."
            )
            boundary_upload = st.file_uploader(
                "Khalifa City GeoJSON",
                type=["geojson", "json"],
                help="Use an organizer/municipal boundary or a carefully drawn geojson.io polygon.",
            )
            if boundary_upload is not None and st.button("Use uploaded AOI", use_container_width=True):
                try:
                    payload = json.loads(boundary_upload.getvalue().decode("utf-8"))
                    if payload.get("type") not in {"FeatureCollection", "Feature", "Polygon", "MultiPolygon"}:
                        raise ValueError("GeoJSON must be a Polygon/MultiPolygon, Feature or FeatureCollection.")
                    target = BASE / "data" / "khalifa_city_boundary.geojson"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps(payload), encoding="utf-8")
                    st.session_state.eo_refresh_nonce += 1
                    st.cache_data.clear()
                    st.success("Custom AOI saved. Rebuilding all EO layers…")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not use this GeoJSON: {exc}")


def _advanced_cache_valid(df, meta):
    required = {
        "geometry_geojson",
        "ndvi_2021",
        "ndbi_2021",
        "ndvi_change",
        "ndbi_change",
        "population_2026",
        "data_confidence",
    }
    return (
        df is not None
        and meta is not None
        and meta.get("advanced_version") == ADVANCED_VERSION
        and required.issubset(df.columns)
    )


@st.cache_data(ttl=21600, show_spinner=False)
def load_data(refresh_nonce: int):
    cached_df, cached_meta = read_cached_dataset(CACHE_CSV, CACHE_META)

    if PUBLIC_SNAPSHOT:
        if _advanced_cache_valid(cached_df, cached_meta):
            return run_analysis(cached_df), cached_meta
        raise EODataError("The published FalconHeat snapshot cache is missing or invalid.")

    if refresh_nonce == 0 and _advanced_cache_valid(cached_df, cached_meta):
        return run_analysis(cached_df), cached_meta

    # Local/research mode can rebuild the live EO dataset.
    raw_df, meta = build_khalifa_dataset(CACHE_CSV, CACHE_META)
    advanced_df, meta = enrich_advanced_dataset(raw_df, meta)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    advanced_df.to_csv(CACHE_CSV, index=False)
    CACHE_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_analysis(advanced_df), meta


try:
    with st.spinner(
        "Building FalconHeat from real EO sources… First refresh can take a few minutes "
        "because historical Sentinel-2 and WorldPop tasks are also processed."
    ):
        df, metadata = load_data(st.session_state.eo_refresh_nonce)
except EODataError as exc:
    st.error("FalconHeat refused to fall back to synthetic data.")
    st.code(str(exc))
    st.stop()
except Exception as exc:
    st.error("The advanced real-data pipeline could not finish.")
    st.code(str(exc))
    st.stop()


def short_date(v):
    return str(v)[:10] if v else "—"


def cloud_text(v):
    return "—" if v is None else f"{float(v):.1f}%"


def safe_sum(series):
    vals = pd.to_numeric(series, errors="coerce")
    if vals.empty:
        return 0.0
    return float(vals.sum()) if vals.notna().any() else np.nan


def fmt_pop(v):
    if pd.isna(v):
        return "Unavailable"
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:,.0f}"


def display_location(r):
    """Competition-safe label: analytical ID first, nearby reference second."""
    cid = str(r.get("cell_id", "")).strip()
    local = str(r.get("local_name", "")).strip()
    if local.lower().startswith("near "):
        local = local[5:].strip()
    if cid and local:
        return f"{cid} · near {local}"
    return cid or local or str(r.get("zone", "Analysis polygon"))


def kpi_card(container, label, value, sub=""):
    container.markdown(
        f"""<div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _driver_fact(r, driver):
    if driver == "Surface temperature":
        anomaly = float(r.get("surface_heat_anomaly_c", 0))
        return (
            f"surface temperature is {r.lst_c:.1f} °C "
            f"({anomaly:+.1f} °C versus the Khalifa City median)"
        )
    if driver == "Built-up land":
        return f"WorldCover maps {r.built_up*100:.1f}% of the polygon as built-up"
    if driver == "Low vegetation":
        return f"current NDVI is low at {r.ndvi:.3f}"
    if driver == "Estimated resident exposure":
        return f"WorldPop estimates about {fmt_pop(r.get('population_2026', np.nan))} residents in the polygon"
    if driver == "Recent change evidence":
        dvi = r.get("ndvi_change", np.nan)
        dbi = r.get("ndbi_change", np.nan)
        signals = []
        if pd.notna(dvi) and dvi < -0.02:
            signals.append(f"NDVI decreased by {abs(dvi):.3f}")
        if pd.notna(dbi) and dbi > 0.02:
            signals.append(f"NDBI increased by {dbi:.3f}")
        if signals:
            return "the conservative 2021→2026 change test flags " + " and ".join(signals)
        return "the selected 2021→2026 comparison does not show a clear change flag"
    return driver.lower()


def why_area(r, concise=False):
    drivers = [
        ("Surface temperature", float(r.get("contrib_temperature", 0))),
        ("Built-up land", float(r.get("contrib_built_up", 0))),
        ("Low vegetation", float(r.get("contrib_low_vegetation", 0))),
        ("Estimated resident exposure", float(r.get("contrib_population", 0))),
        ("Recent change evidence", float(r.get("contrib_urban_change", 0))),
    ]
    drivers = sorted(drivers, key=lambda x: x[1], reverse=True)
    first, second = drivers[0][0], drivers[1][0]
    if concise:
        return f"Why: {_driver_fact(r, first)}; {_driver_fact(r, second)}."
    return (
        f"<b>{display_location(r)}</b> ranks <b>{r.risk_level}</b> at "
        f"<b>{r.risk_score:.0f}/100</b> mainly because {_driver_fact(r, first)} "
        f"and {_driver_fact(r, second)}."
    )


df["display_name"] = df.apply(display_location, axis=1)

s2_date = short_date(metadata.get("sentinel2", {}).get("acquisition"))
ls_date = short_date(metadata.get("landsat", {}).get("acquisition"))
hist_date = short_date(metadata.get("sentinel2_historical", {}).get("acquisition"))
worldpop_ok = df["population_2026"].notna().any()
change_ok = df[["ndvi_change", "ndbi_change"]].notna().all(axis=1).any()

# ------------------------------ HERO ----------------------------------------
st.markdown(
    f"""
<div class="hero">
<div class="eyebrow">Urban Heat Intelligence · Khalifa City · Abu Dhabi</div>
<div class="hero-title">FalconHeat AI</div>
<div class="hero-sub">
<b>From satellite observation to explainable heat-mitigation decisions.</b><br>
FalconHeat combines current land-surface temperature, vegetation, built-up land,
population exposure and summer-matched 2021→2026 change evidence within a defined Khalifa City study area, not all of Abu Dhabi city.
Every priority score is decomposable into its drivers and every source is traceable.
</div>
<div class="badge">● REAL EO · PUBLIC COMPETITION SNAPSHOT</div>
</div>
""",
    unsafe_allow_html=True,
)

aoi_source_short = (
    "Custom GeoJSON"
    if metadata.get("aoi_boundary_source") == "User-supplied Khalifa City GeoJSON"
    else ("OSM / Nominatim" if not metadata.get("aoi_boundary_is_fallback") else "Curated study polygon")
)
source_cards = [
    ("LANDSAT", ls_date, "Surface temperature"),
    ("SENTINEL-2", s2_date, "Current NDVI / NDBI"),
    ("HISTORICAL S2", hist_date, "2021 summer baseline" if change_ok else "Unavailable"),
    ("WORLDCOVER", "2021", "Built-up structural baseline"),
    ("WORLDPOP", "2026" if worldpop_ok else "—", "Estimated residents" if worldpop_ok else "Unavailable"),
    ("KHALIFA AOI", aoi_source_short, "Clipped study boundary · not an official municipal boundary" if metadata.get("aoi_boundary_is_fallback") else "Clipped study boundary"),
]
for start in (0, 3):
    source_cols = st.columns(3)
    for c, (title, date, desc) in zip(source_cols, source_cards[start:start+3]):
        c.markdown(
            f'<div class="card"><div class="smallcaps">{title}</div>'
            f'<div class="source-date">{date}</div><div class="muted">{desc}</div></div>',
            unsafe_allow_html=True,
        )
    if start == 0:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ------------------------------ KPIs ----------------------------------------
core_sources_ok = (
    metadata.get("landsat", {}).get("acquisition")
    and metadata.get("sentinel2", {}).get("acquisition")
    and metadata.get("worldcover", {}).get("item_id")
)
pop_sources_ok = bool(worldpop_ok)
hist_sources_ok = bool(change_ok)
boundary_is_fallback = bool(metadata.get("aoi_boundary_is_fallback"))

integrity_bits = [
    "Core EO ✓" if core_sources_ok else "Core EO incomplete",
    "Historical S2 ✓" if hist_sources_ok else "Historical S2 unavailable",
    "WorldPop ✓" if pop_sources_ok else "WorldPop unavailable",
    "AOI: curated study polygon" if boundary_is_fallback else "AOI boundary ✓",
]
st.markdown(
    '<div class="source-note" style="margin:12px 0 18px">'
    '<b>Source availability:</b> ' + " · ".join(integrity_bits) +
    ('<br><span class="muted">The current AOI is a curated study polygon, not an official municipal boundary.</span>'
     if boundary_is_fallback else '') +
    '</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="section-label">Executive snapshot</div><div class="section-title">What needs attention first?</div>', unsafe_allow_html=True)

high = df[df["risk_level"].isin(["High", "Very High"])]
priority_pop = safe_sum(high["population_2026"]) if worldpop_ok else np.nan
top = df.iloc[0]
clear_change_rows = (
    df[df.get("clear_change_flag", False).astype(bool)]
    if "clear_change_flag" in df.columns else df.iloc[0:0]
)
strongest_change = (
    clear_change_rows.loc[clear_change_rows["urban_change_norm"].idxmax()]
    if change_ok and not clear_change_rows.empty and clear_change_rows["urban_change_norm"].notna().any()
    else None
)

hottest = df.loc[df["surface_heat_anomaly_c"].idxmax()]
row1 = st.columns(3)
kpi_card(row1[0], "Top priority polygon", f"{top.risk_score:.0f}/100", display_location(top))
kpi_card(row1[1], "Highest polygon-median LST", f"{df.lst_c.max():.1f} °C", display_location(df.loc[df.lst_c.idxmax()]))
kpi_card(row1[2], "Hottest surface anomaly", f"{hottest.surface_heat_anomaly_c:+.1f} °C", f"above Khalifa City median · {display_location(hottest)}")

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
row2 = st.columns(3)
kpi_card(
    row2[0],
    "Est. residents in High / Very High polygons",
    fmt_pop(priority_pop),
    "WorldPop model estimate · not a census count",
)
kpi_card(row2[1], "Median evidence completeness", f"{df.data_confidence.median():.0f}%", "Source coverage / cloud / exposure availability")
kpi_card(
    row2[2],
    "2021→2026 change-stress flags",
    strongest_change.get("cell_id", "None") if strongest_change is not None else ("None detected" if change_ok else "Unavailable"),
    display_location(strongest_change) if strongest_change is not None else ("No NDVI loss >0.02 or NDBI gain >0.02" if change_ok else "Historical comparison unavailable"),
)

st.markdown(
    f"""<div class="insight" style="margin:14px 0 12px">
    <div class="smallcaps">EXECUTIVE INSIGHT</div>
    {why_area(top)}
    {" Across the current AOI, WorldPop estimates <b>" + fmt_pop(priority_pop) + "</b> residents inside High/Very High priority polygons." if worldpop_ok else ""}
    </div>""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="source-note" style="margin:12px 0 20px">
<b>Interpretation:</b> FalconHeat is an <b>explainable relative planning-priority index</b>.
It is not a medical heat-health threshold. Landsat LST is surface temperature, not air temperature.
WorldCover 2021 is a structural built-up baseline. WorldPop values are model-based population estimates.
The 2021→2026 Sentinel comparison uses the same Jul–Sep seasonal window to reduce seasonal bias. Small index differences inside ±0.02 are treated as inconclusive rather than amplified into change priority.
</div>
""",
    unsafe_allow_html=True,
)

# ------------------------------ HELPERS -------------------------------------
priority_colors = {
    "Low": "#39c58a",
    "Moderate": "#f4c95d",
    "High": "#ff8c42",
    "Very High": "#ff4d4d",
}


def _hex_interp(a, b, t):
    a = a.lstrip("#"); b = b.lstrip("#")
    ar, ag, ab = int(a[:2],16), int(a[2:4],16), int(a[4:],16)
    br, bg, bb = int(b[:2],16), int(b[2:4],16), int(b[4:],16)
    t = float(np.clip(t, 0, 1))
    return "#{:02x}{:02x}{:02x}".format(
        int(ar+(br-ar)*t), int(ag+(bg-ag)*t), int(ab+(bb-ab)*t)
    )


def continuous_color(value, lo, hi, low="#35c99a", high="#ff5050"):
    if pd.isna(value):
        return "#60736d"
    t = 0.5 if hi == lo else (float(value)-lo)/(hi-lo)
    return _hex_interp(low, high, t)


def geometry_from_row(r):
    geom = r.get("geometry_geojson")
    return json.loads(geom) if isinstance(geom, str) else geom


def make_map(layer, rows):
    boundary = metadata.get("aoi_boundary_geojson")
    center = [float(df.latitude.mean()), float(df.longitude.mean())]
    m = folium.Map(location=center, zoom_start=13, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap",
        max_zoom=19,
    ).add_to(m)
    Fullscreen(position="topright").add_to(m)
    MiniMap(toggle_display=True, tile_layer="OpenStreetMap").add_to(m)

    if boundary:
        folium.GeoJson(
            boundary,
            name="Khalifa City AOI",
            style_function=lambda _: {
                "color": "#d3eee6", "weight": 3, "fill": False, "dashArray": "7 5"
            },
            tooltip=f"Khalifa City AOI · {metadata.get('aoi_boundary_source','study boundary')}",
        ).add_to(m)

    if layer == "Priority":
        lo, hi = 0, 100
    elif layer == "Surface temperature":
        lo, hi = float(df.lst_c.min()), float(df.lst_c.max())
    elif layer == "Estimated resident exposure":
        vals = pd.to_numeric(df.population_2026, errors="coerce")
        lo, hi = float(vals.min()) if vals.notna().any() else 0, float(vals.max()) if vals.notna().any() else 1
    elif layer == "Vegetation change":
        vals = pd.to_numeric(df.ndvi_change, errors="coerce")
        lo, hi = float(vals.min()) if vals.notna().any() else -1, float(vals.max()) if vals.notna().any() else 1
    else:
        lo, hi = 0, 1

    for _, r in rows.iterrows():
        if layer == "Priority":
            color = priority_colors[r.risk_level]
            value_line = f"Priority: {r.risk_score:.1f}/100 ({r.risk_level})"
        elif layer == "Surface temperature":
            color = continuous_color(r.lst_c, lo, hi)
            value_line = f"LST: {r.lst_c:.2f} °C ({r.surface_heat_anomaly_c:+.2f} °C vs AOI median)"
        elif layer == "Estimated resident exposure":
            color = continuous_color(r.population_2026, lo, hi, "#6ed6e6", "#ef4e66")
            value_line = f"WorldPop 2026: {fmt_pop(r.population_2026)}"
        elif layer == "Vegetation change":
            # negative change (loss) -> red; positive -> green
            v = r.ndvi_change
            if pd.isna(v):
                color = "#60736d"
            elif v < 0:
                color = continuous_color(abs(v), 0, max(abs(lo), .001), "#f3c65e", "#ff4d4d")
            else:
                color = continuous_color(v, 0, max(hi, .001), "#b9d98b", "#2dd49f")
            value_line = f"NDVI change 2021→2026: {v:+.4f}" if pd.notna(v) else "NDVI change unavailable"
        else:
            color = priority_colors[r.risk_level]
            value_line = ""

        pop_line = fmt_pop(r.population_2026)
        ndvi_hist = "—" if pd.isna(r.ndvi_2021) else f"{r.ndvi_2021:.3f}"
        popup = f"""
        <div style='font-family:Arial;width:340px'>
          <div style='font-size:17px;font-weight:800'>{display_location(r)}</div>
          <div style='font-size:12px;color:#60736d;margin:4px 0 8px'>Khalifa City analysis polygon</div>
          <b>{value_line}</b><hr>
          <table style='width:100%;font-size:13px'>
          <tr><td>Surface temperature</td><td>{r.lst_c:.1f} °C</td></tr>
          <tr><td>Heat anomaly</td><td>{r.surface_heat_anomaly_c:+.1f} °C</td></tr>
          <tr><td>Current NDVI</td><td>{r.ndvi:.3f}</td></tr>
          <tr><td>NDVI 2021</td><td>{ndvi_hist}</td></tr>
          <tr><td>Built-up</td><td>{r.built_up*100:.1f}%</td></tr>
          <tr><td>Population</td><td>{pop_line}</td></tr>
          <tr><td>Evidence completeness</td><td>{r.data_confidence:.0f}%</td></tr>
          </table>
          <hr><b>Top driver:</b> {r.top_driver}<br>
          <b>Action:</b> {r.recommendation}
        </div>"""
        folium.GeoJson(
            geometry_from_row(r),
            style_function=lambda _, c=color: {
                "color": c, "weight": 2, "fill": True,
                "fillColor": c, "fillOpacity": .50,
            },
            tooltip=f"{display_location(r)} · {value_line}",
            popup=folium.Popup(popup, max_width=390),
        ).add_to(m)

    if boundary:
        # fit bounds using metadata bbox for reliable rendering
        west, south, east, north = metadata["aoi_bbox_wgs84"]
        m.fit_bounds([[south, west], [north, east]], padding=(15, 15))
    folium.LayerControl(collapsed=True).add_to(m)
    return m


# ------------------------------ TABS ----------------------------------------
tab_heat, tab_change, tab_exposure, tab_scenario, tab_evidence = st.tabs(
    ["🔥 Heat Priority", "🏙️ Urban Change", "👥 Exposure", "🧪 Scenario Lab", "🔎 Evidence & Export"]
)

with tab_heat:
    controls1, controls2, controls3 = st.columns([1.1, 1.2, 1])
    with controls1:
        layer = st.selectbox(
            "Map layer",
            ["Priority", "Surface temperature", "Estimated resident exposure", "Vegetation change"],
        )
    with controls2:
        levels = st.multiselect(
            "Priority classes",
            ["Low", "Moderate", "High", "Very High"],
            default=["Low", "Moderate", "High", "Very High"],
        )
    with controls3:
        min_score = st.slider("Minimum priority score", 0, 100, 0)

    view = df[df.risk_level.isin(levels) & (df.risk_score >= min_score)]
    st.caption(f"Showing {len(view)} of {len(df)} polygons. Filters affect the map and queue; overview metrics and analysis below use the full study area.")
    if view.empty:
        st.info("No polygons match these filters. Lower the minimum score or select another priority class.")
    mapcol, queuecol = st.columns([2.35, 1])
    with mapcol:
        st.markdown(f"### Khalifa City · {layer}")
        if layer == "Priority":
            st.caption("Low: 0–<25 · Moderate: 25–<50 · High: 50–<75 · Very High: 75–100. Relative planning classes, not health thresholds.")
        elif layer == "Surface temperature":
            st.caption(f"Green → red: {df.lst_c.min():.1f}–{df.lst_c.max():.1f} °C. Each polygon shows median surface temperature, not pixel maximum or air temperature.")
        elif layer == "Estimated resident exposure":
            st.caption("Cyan → red: lower → higher modeled resident totals per polygon. Grey: unavailable.")
        else:
            st.caption("Red: NDVI decrease · green: increase · grey: unavailable. Colours show relative change magnitude, not statistical significance.")
        st_folium(make_map(layer, view), key="heat_map", height=650, use_container_width=True, returned_objects=[])
    with queuecol:
        st.markdown("### Priority queue")
        st.caption("EXPLAINABLE INDEX · DESCENDING")
        for i, r in view.reset_index(drop=True).iterrows():
            why_html = ""
            if r.risk_level in ("High", "Very High"):
                why_html = f'<div class="rank-insight">{why_area(r, concise=True)}</div>'

            card_html = (
                '<div class="rank">'
                f'<div class="rank-name">{i+1:02d} &nbsp; {display_location(r)}</div>'
                f'<div class="rank-meta">'
                f'<span style="color:{priority_colors[r.risk_level]};font-weight:850">'
                f'{r.risk_level.upper()}</span>'
                f' · {r.risk_score:.0f}/100 · {r.lst_c:.1f} °C · {r.top_driver}'
                f'</div>'
                f'{why_html}'
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    st.markdown('<div class="section-label">Explainability</div><div class="section-title">Why did this cell rank here?</div>', unsafe_allow_html=True)
    zone_display = {row.zone: display_location(row) for _, row in df.iterrows()}
    selected_zone = st.selectbox(
        "Inspect analysis polygon",
        df.zone.tolist(),
        key="explain_zone",
        format_func=lambda z: zone_display.get(z, z),
    )
    r = df.loc[df.zone.eq(selected_zone)].iloc[0]

    er1 = st.columns(3)
    kpi_card(er1[0], "Priority", f"{r.risk_score:.1f}/100", r.risk_level)
    kpi_card(er1[1], "Surface temperature", f"{r.lst_c:.1f} °C", f"{r.surface_heat_anomaly_c:+.1f} °C vs Khalifa median")
    kpi_card(
        er1[2],
        "Current NDVI",
        f"{r.ndvi:.3f}",
        f"{r.ndvi_change:+.3f} since summer 2021" if pd.notna(r.ndvi_change) else "2021 comparison unavailable",
    )
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    er2 = st.columns(3)
    kpi_card(er2[0], "WorldCover built-up", f"{r.built_up*100:.1f}%", "2021 structural baseline")
    kpi_card(er2[1], "Estimated residents", fmt_pop(r.population_2026), "WorldPop 2026 model estimate")
    kpi_card(er2[2], "Evidence completeness", f"{r.data_confidence:.0f}%", "Not a statistical confidence interval")

    st.markdown(
        f"""<div class="insight" style="margin:12px 0 18px">
        <div class="smallcaps">WHY THIS AREA?</div>
        {why_area(r)}
        </div>""",
        unsafe_allow_html=True,
    )

    contributions = pd.DataFrame({
        "Driver": ["Temperature", "Built-up", "Low vegetation", "Population", "Urban change"],
        "Points": [
            r.contrib_temperature, r.contrib_built_up, r.contrib_low_vegetation,
            r.contrib_population, r.contrib_urban_change,
        ],
    })
    c1, c2 = st.columns([1.35, 1])
    with c1:
        fig = go.Figure(
            go.Bar(
                x=contributions.Points,
                y=contributions.Driver,
                orientation="h",
                text=[f"{x:.1f} pts" for x in contributions.Points],
                textposition="auto",
            )
        )
        fig.update_layout(
            title="Score contribution by driver",
            height=380,
            margin=dict(l=10, r=10, t=50, b=20),
            paper_bgcolor="#061713",
            plot_bgcolor="#0b241e",
            font_color="#dcebe6",
            xaxis_title="Priority points",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown(
            f"""<div class="action">
            <div class="smallcaps">TOP DRIVER</div>
            <b style="font-size:1.3rem">{r.top_driver}</b><br><br>
            <b>Recommended planning response</b><br>{r.recommendation}<br><br>
            <span class="muted">Evidence completeness: {r.data_confidence:.0f}% ·
            This is evidence completeness, not a statistical confidence interval.</span>
            </div>""",
            unsafe_allow_html=True,
        )

with tab_change:
    st.markdown('<div class="section-label">Temporal intelligence</div><div class="section-title">What changed from summer 2021 to summer 2026?</div>', unsafe_allow_html=True)

    if not change_ok:
        st.warning("Historical Sentinel-2 comparison is unavailable in this refresh.")
        st.code(metadata.get("sentinel2_historical", {}).get("error", "No details"))
    else:
        ndvi_decrease_cells = int((df.ndvi_change < 0).sum())
        ndbi_increase_cells = int((df.ndbi_change > 0).sum())
        clear_flags = int(df.get("clear_change_flag", pd.Series(False, index=df.index)).sum())
        ch1, ch2, ch3, ch4 = st.columns(4)
        ch1.metric("NDVI decrease polygons", ndvi_decrease_cells)
        ch2.metric("NDBI increase polygons", ndbi_increase_cells)
        ch3.metric("Change-stress flags", clear_flags, "NDVI loss / NDBI gain >0.02")
        ch4.metric("Median ΔNDVI / ΔNDBI", f"{df.ndvi_change.median():+.4f} / {df.ndbi_change.median():+.4f}")

        if ndbi_increase_cells == 0:
            st.markdown(
                """<div class="warn-note">
                <b>Current finding:</b> this summer-matched Sentinel-2 comparison shows
                <b>no positive NDBI increase in any analysis polygon</b>. Negative ΔNDBI is
                not presented as urban expansion. Small NDVI decreases are shown descriptively,
                but only NDVI losses greater than 0.02 or NDBI gains greater than 0.02 contribute to
                the priority model.
                </div>""",
                unsafe_allow_html=True,
            )

        left, right = st.columns([1.45, 1])
        with left:
            st_folium(make_map("Vegetation change", df), key="change_map", height=560, use_container_width=True, returned_objects=[])
        with right:
            q = df.sort_values("urban_change_norm", ascending=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="NDVI decrease magnitude",
                y=q["display_name"],
                x=(q.vegetation_loss.fillna(0)),
                orientation="h",
            ))
            fig.add_trace(go.Bar(
                name="Positive NDBI change",
                y=q["display_name"],
                x=(q.ndbi_gain.fillna(0)),
                orientation="h",
            ))
            fig.update_layout(
                barmode="stack",
                title="Observed 2021→2026 spectral changes",
                height=560,
                margin=dict(l=10,r=10,t=50,b=20),
                paper_bgcolor="#061713", plot_bgcolor="#0b241e", font_color="#dcebe6",
                xaxis_title="Observed index-change magnitude",
                yaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

        change_cols = [
            "display_name","ndvi_2021","ndvi","ndvi_change",
            "ndbi_2021","ndbi","ndbi_change","sar_vv_change_db"
        ]
        show_change = df[[c for c in change_cols if c in df.columns]].copy()
        st.dataframe(
            show_change.rename(columns={
                "display_name":"Analysis polygon",
                "ndvi_2021":"NDVI 2021","ndvi":"NDVI 2026","ndvi_change":"ΔNDVI",
                "ndbi_2021":"NDBI 2021","ndbi":"NDBI 2026","ndbi_change":"ΔNDBI",
                "sar_vv_change_db":"Sentinel-1 ΔVV dB",
            }),
            use_container_width=True,
            hide_index=True,
        )

        sar_meta = metadata.get("sentinel1", {})
        if sar_meta.get("status") == "unavailable":
            st.info(
                "Sentinel-1 GRD evidence was not available for a matched same-track pair in this refresh. "
                "It is optional and is never replaced with synthetic values."
            )
        elif df["sar_vv_change_db"].notna().any():
            st.markdown(
                f"""<div class="warn-note"><b>Sentinel-1 diagnostic:</b>
                matched relative orbit {sar_meta.get('relative_orbit')} ·
                {sar_meta.get('historical_acquisition')} → {sar_meta.get('current_acquisition')}.<br>
                The ΔVV layer is an <b>uncalibrated same-track GRD amplitude-change diagnostic</b>;
                it is intentionally excluded from the priority score.</div>""",
                unsafe_allow_html=True,
            )

with tab_exposure:
    st.markdown('<div class="section-label">Human exposure</div><div class="section-title">Where do heat and people overlap?</div>', unsafe_allow_html=True)
    if not worldpop_ok:
        st.warning("WorldPop 2026 exposure is unavailable in this refresh. FalconHeat reweighted the score without inventing population values.")
        st.code(metadata.get("worldpop", {}).get("error", metadata.get("worldpop", {}).get("errors", "No details")))
    else:
        total_pop = safe_sum(df.population_2026)
        high_pop = safe_sum(high.population_2026)
        hottest_quartile = df[df.lst_c >= df.lst_c.quantile(.75)]
        hot_pop = safe_sum(hottest_quartile.population_2026)

        p1,p2,p3,p4 = st.columns(4)
        kpi_card(p1, "Estimated residents in AOI", fmt_pop(total_pop), "WorldPop 2026 model estimate")
        kpi_card(
            p2,
            "Est. residents in High / Very High",
            fmt_pop(high_pop),
            f"{(high_pop/total_pop*100):.0f}% of modeled AOI residents" if total_pop else "WorldPop estimate",
        )
        kpi_card(p3, "Est. residents in hottest quartile", fmt_pop(hot_pop), "Based on Landsat LST quartile")
        kpi_card(p4, "WorldPop grid", "100 m", "Model-based population surface")

        left,right = st.columns([1.4,1])
        with left:
            st_folium(make_map("Estimated resident exposure", df), key="exposure_map", height=570, use_container_width=True, returned_objects=[])
        with right:
            q=df.sort_values("population_2026",ascending=True)
            fig=go.Figure(go.Bar(
                x=q.population_2026,
                y=q["display_name"],
                orientation="h",
                customdata=q.risk_score,
                hovertemplate="%{y}<br>Population: %{x:,.0f}<br>Priority: %{customdata:.1f}/100<extra></extra>",
            ))
            fig.update_layout(
                title="Estimated population exposure by polygon",
                height=570,
                margin=dict(l=10,r=10,t=50,b=20),
                paper_bgcolor="#061713",plot_bgcolor="#0b241e",font_color="#dcebe6",
                xaxis_title="WorldPop estimated people",yaxis_title=""
            )
            st.plotly_chart(fig,use_container_width=True)

        st.caption(
            "WorldPop exposure values are gridded model estimates and should be interpreted as approximate planning exposure, not official census counts."
        )

with tab_scenario:
    st.markdown('<div class="section-label">Planning simulator</div><div class="section-title">What if we cool a hotspot?</div>', unsafe_allow_html=True)
    st.markdown(
        """Use the controls below to test an **illustrative intervention scenario**.
        FalconHeat recalculates the same transparent priority index using your assumed
        changes. It does **not** claim these sliders predict the physical effect of an intervention."""
    )

    zone = st.selectbox(
        "Analysis polygon",
        df.zone.tolist(),
        key="scenario_zone",
        format_func=lambda z: zone_display.get(z, z),
    )
    idx = int(df.index[df.zone.eq(zone)][0])
    base = df.loc[idx]

    s1,s2,s3,s4 = st.columns(4)
    with s1:
        temp_drop = st.slider("Assumed LST reduction (°C)", 0.0, 6.0, 2.0, .25)
    with s2:
        ndvi_gain = st.slider("Assumed NDVI increase", 0.0, .20, .05, .01)
    with s3:
        built_reduction = st.slider("Assumed effective exposed-surface reduction", 0.0, .20, .05, .01)
    with s4:
        exposure_reduction = st.slider("Exposure reduction (%)", 0, 50, 10, 5)

    scenario = scenario_score(
        df, idx,
        lst_delta_c=-temp_drop,
        ndvi_delta=ndvi_gain,
        built_delta=-built_reduction,
        exposure_reduction_pct=exposure_reduction,
    )

    before, after, improvement = st.columns(3)
    before.metric("Current priority", f"{base.risk_score:.1f}/100", base.risk_level)
    after.metric("Scenario priority", f"{scenario['score']:.1f}/100", scenario["level"])
    improvement.metric("Priority reduction", f"{base.risk_score-scenario['score']:.1f} points")

    comp_before = {
        "Temperature": base.contrib_temperature,
        "Built-up": base.contrib_built_up,
        "Low vegetation": base.contrib_low_vegetation,
        "Population": base.contrib_population,
        "Change evidence": base.contrib_urban_change,
    }
    comp_after = {
        "Temperature": scenario["contributions"].get("temperature",0),
        "Built-up": scenario["contributions"].get("built_up",0),
        "Low vegetation": scenario["contributions"].get("low_vegetation",0),
        "Population": scenario["contributions"].get("population",0),
        "Change evidence": scenario["contributions"].get("urban_change",0),
    }
    drivers=list(comp_before)
    fig=go.Figure()
    fig.add_trace(go.Bar(name="Current",x=drivers,y=[comp_before[x] for x in drivers]))
    fig.add_trace(go.Bar(name="Scenario",x=drivers,y=[comp_after[x] for x in drivers]))
    fig.update_layout(
        barmode="group",title="Explainable driver contribution: current vs scenario",
        height=420,paper_bgcolor="#061713",plot_bgcolor="#0b241e",font_color="#dcebe6",
        yaxis_title="Priority points"
    )
    st.plotly_chart(fig,use_container_width=True)
    st.markdown(
        f"""<div class="warn-note"><b>Scenario assumptions:</b>
        LST {base.lst_c:.1f}→{scenario['lst_c']:.1f} °C ·
        NDVI {base.ndvi:.3f}→{scenario['ndvi']:.3f} ·
        Effective exposed/built-up share {base.built_up*100:.1f}%→{scenario['built_up']*100:.1f}% ·
        Exposure reduction {exposure_reduction}%.<br>
        <b>This is a decision-support sensitivity test, not a forecast.</b> Because FalconHeat uses relative AOI normalization, large slider changes can create large score shifts; do not interpret the point reduction as a predicted real-world cooling benefit.</div>""",
        unsafe_allow_html=True,
    )

with tab_evidence:
    st.markdown('<div class="section-label">Reproducibility</div><div class="section-title">Evidence, provenance & export</div>', unsafe_allow_html=True)

    e1,e2,e3 = st.columns(3)
    e1.metric("Mean evidence completeness", f"{df.data_confidence.mean():.0f}%")
    e2.metric("Scene footprint coverage (S2)", f"{metadata.get('sentinel2',{}).get('aoi_coverage_pct','—')}%")
    e3.metric("AOI source", aoi_source_short)
    st.caption("Evidence completeness is a metadata-based heuristic, not accuracy or measured valid-pixel coverage. The current comparison uses one acquisition day per year, not a seasonal composite.")

    st.markdown("### Source trace")
    source_text = f"""
**Landsat Collection 2 Level-2**  
- Acquisition: `{metadata.get('landsat',{}).get('acquisition','—')}`  
- Item(s): `{metadata.get('landsat',{}).get('item_id','—')}`  
- Scene cloud metadata: `{cloud_text(metadata.get('landsat',{}).get('scene_cloud_cover_pct'))}`

**Sentinel-2 Level-2A — current**  
- Acquisition: `{metadata.get('sentinel2',{}).get('acquisition','—')}`  
- Item(s): `{metadata.get('sentinel2',{}).get('item_id','—')}`  
- Scene cloud metadata: `{cloud_text(metadata.get('sentinel2',{}).get('scene_cloud_cover_pct'))}`

**Sentinel-2 Level-2A — historical**  
- Acquisition: `{metadata.get('sentinel2_historical',{}).get('acquisition','Unavailable')}`  
- Item(s): `{metadata.get('sentinel2_historical',{}).get('item_id','—')}`

**ESA WorldCover**  
- Year: `2021`  
- Item(s): `{metadata.get('worldcover',{}).get('item_id','—')}`

**WorldPop Global2**  
- Year: `{metadata.get('worldpop',{}).get('year','Unavailable')}`  
- Resolution: `{metadata.get('worldpop',{}).get('resolution','—')}`  
- Successful polygons: `{metadata.get('worldpop',{}).get('successful_cells','—')}/{metadata.get('worldpop',{}).get('total_cells','—')}`

**Khalifa City AOI**  
- Source: `{metadata.get('aoi_boundary_source','—')}`  
- Label: `{metadata.get('aoi_boundary_label','—')}`
"""
    st.markdown(source_text)

    st.markdown("### 813 Challenge Imagery Lab")
    st.caption(
        "Optional: load an organizer-provided 813 GeoTIFF as competition-native visual evidence. "
        "FalconHeat will inspect and preview it, but will not silently use unknown bands in the priority score."
    )
    tif = st.file_uploader(
        "Upload 813 GeoTIFF",
        type=["tif", "tiff"],
        key="evidence_813",
    )
    if tif is not None:
        tmp_path = None
        try:
            import rasterio
            import matplotlib.pyplot as plt
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
                tmp.write(tif.getvalue())
                tmp_path = tmp.name

            with rasterio.open(tmp_path) as src:
                b1,b2,b3,b4 = st.columns(4)
                b1.metric("Bands", src.count)
                b2.metric("Width × height", f"{src.width} × {src.height}")
                b3.metric("CRS", str(src.crs) if src.crs else "Unknown")
                if src.transform:
                    px = abs(src.transform.a)
                    b4.metric("Pixel size", f"{px:.3g} {('m' if src.crs and src.crs.is_projected else 'deg')}")
                else:
                    b4.metric("Pixel size", "—")

                st.caption(
                    f"Bounds: {tuple(round(float(v), 5) for v in src.bounds)} · "
                    f"Data type: {src.dtypes[0] if src.dtypes else '—'}"
                )

                max_band = int(src.count)
                if max_band >= 3:
                    default = [1, min(2,max_band), min(3,max_band)]
                    rband = st.number_input("Preview red-channel band", 1, max_band, default[0], key="813r")
                    gband = st.number_input("Preview green-channel band", 1, max_band, default[1], key="813g")
                    bband = st.number_input("Preview blue-channel band", 1, max_band, default[2], key="813b")
                    arr = src.read([int(rband),int(gband),int(bband)], out_shape=(3, min(src.height,900), min(src.width,900))).astype("float32")
                    rgb=np.zeros_like(arr)
                    for j in range(3):
                        band=arr[j]
                        valid=band[np.isfinite(band)]
                        if valid.size:
                            lo,hi=np.percentile(valid,[2,98])
                            rgb[j]=np.clip((band-lo)/(hi-lo if hi>lo else 1),0,1)
                    fig,ax=plt.subplots(figsize=(8,6))
                    ax.imshow(np.moveaxis(rgb,0,-1))
                    ax.set_title(f"813 quicklook · bands {int(rband)}/{int(gband)}/{int(bband)}")
                    ax.axis("off")
                    st.pyplot(fig,use_container_width=True)
                    plt.close(fig)
                    st.info(
                        "Band semantics depend on the 813 product documentation. "
                        "This quicklook is visual evidence only until band wavelengths/calibration are confirmed."
                    )
                else:
                    band=src.read(1,out_shape=(min(src.height,900),min(src.width,900))).astype("float32")
                    fig,ax=plt.subplots(figsize=(8,6))
                    ax.imshow(band,cmap="gray")
                    ax.set_title("813 single-band quicklook")
                    ax.axis("off")
                    st.pyplot(fig,use_container_width=True)
                    plt.close(fig)
        except Exception as exc:
            st.error(f"Could not inspect this GeoTIFF: {exc}")
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

    st.markdown("### Export reproducible outputs")
    st.caption("Exports include all study polygons and baseline results; map filters and illustrative scenarios do not alter them.")
    c1,c2 = st.columns(2)
    csv_bytes=df.to_csv(index=False).encode("utf-8")
    export_metadata = dict(metadata)
    export_metadata["analysis_model"] = {
        "version": "4.4", "type": "weighted planning-priority index; no trained ML inference",
        "nominal_weights": BASE_WEIGHTS,
        "normalization": "AOI min-max for T/B/V; log1p then min-max for P; fixed scale for C",
        "change_formula": "C = 0.5*clip((-delta_ndvi-0.02)/0.08,0,1) + 0.5*clip((delta_ndbi-0.02)/0.08,0,1)",
        "score_formula": "100 * sum(available weight * component) / sum(available weights)",
        "classes": {"Low": "0 <= H < 25", "Moderate": "25 <= H < 50", "High": "50 <= H < 75", "Very High": "75 <= H <= 100"},
        "scope": "Full study area; UI filters do not change normalization or exports",
    }
    meta_bytes=json.dumps(export_metadata,indent=2,allow_nan=False).encode("utf-8")
    c1.download_button(
        "⬇ Download analyzed CSV",
        data=csv_bytes,
        file_name="falconheat_khalifa_city_advanced.csv",
        mime="text/csv",
        use_container_width=True,
    )
    c2.download_button(
        "⬇ Download provenance JSON",
        data=meta_bytes,
        file_name="falconheat_khalifa_city_provenance.json",
        mime="application/json",
        use_container_width=True,
    )

    show_cols=[
        "display_name","cell_id","local_name","lst_c","surface_heat_anomaly_c","ndvi_2021","ndvi",
        "ndvi_change","ndbi_2021","ndbi","ndbi_change","built_up","population_2026",
        "population_density_km2","sar_vv_change_db","data_confidence","risk_score",
        "risk_level","top_driver","recommendation"
    ]
    display=df[[c for c in show_cols if c in df.columns]].copy()
    if "built_up" in display:
        display["built_up"]=display["built_up"]*100
    st.dataframe(display,use_container_width=True,hide_index=True)

    with st.expander("Model transparency"):
        st.markdown(
            """
The priority score is intentionally **not a black-box model**. It is a weighted
decision index over the current Khalifa City analysis polygons. Temperature, built-up,
vegetation and log-population use AOI min-max normalization; change stress uses a
fixed tolerance and scale. This dashboard does not use a trained deep-learning model.
The five nominal weights are 35% temperature, 20% built-up, 15% low vegetation,
15% population exposure and 15% urban-change stress. If an optional data source is
missing, its weight is redistributed across the available measured components.

**Important limitations**
- The score is relative to the current AOI; changing the AOI can change ranks.
- Landsat LST measures land-surface temperature, not 2 m air temperature.
- WorldCover 2021 is a structural baseline and not a 2026 impervious-surface map.
- WorldPop is a model-based gridded estimate, not an official census.
- NDVI/NDBI change is an index signal, not a cadastral urban-growth measurement. Only NDVI loss >0.02 or NDBI gain >0.02 contributes to change stress; negative NDBI change is not an expansion flag.
- Sentinel-1 GRD change, when available, is diagnostic only and excluded from the score.
"""
        )

st.caption(
    "FalconHeat AI · Team 971 Liftoff · Khalifa City, Abu Dhabi · "
    "Real Earth-observation inputs · Explainable planning-priority PoC"
)

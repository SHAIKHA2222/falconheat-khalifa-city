# FalconHeat AI
## Advanced Khalifa City Urban Heat Intelligence

**Team:** 971 Liftoff  
**Challenge:** Urban Expansion, Land Use Change & Heat Risk  
**Study area:** Khalifa City, Abu Dhabi, UAE  
**Status:** Real-data Earth-observation Proof of Concept

FalconHeat AI is an explainable geospatial decision-support system that identifies which parts of Khalifa City should receive heat-mitigation attention first. The advanced dashboard combines **current heat**, **vegetation**, **built-up land**, **population exposure**, and **2021→2026 urban-change signals** inside a clipped Khalifa City study area of interest.

The system deliberately separates **measured/derived evidence** from **decision logic**. Satellite and population inputs remain traceable to their source products, while the final 0–100 score is clearly labelled as a **relative planning-priority index**, not a medical heat-health threshold.

---

## What the advanced version adds

Compared with the earlier PoC, this version includes:

- clipped Khalifa City study-polygon masking instead of a rectangular grid;
- **summer-matched Sentinel-2 change analysis: 2021 → 2026**;
- **WorldPop 2026 population exposure** at 100 m resolution;
- land-surface heat anomaly relative to the Khalifa City median;
- an explainable five-driver priority model;
- per-cell score contribution breakdown;
- an evidence-completeness/confidence indicator;
- an intervention **Scenario Lab**;
- optional Sentinel-1 same-track GRD amplitude-change evidence;
- CSV and provenance JSON export;
- an **813 Challenge Imagery Lab** for organizer-provided GeoTIFF inspection/quicklooks without pretending unknown bands are validated indicators;
- optional custom GeoJSON AOI override for organizer/municipal boundaries.

No synthetic values are inserted if a real-data layer is unavailable.

---

## Real data sources

| Indicator | Source | FalconHeat use |
|---|---|---|
| Land-surface temperature | **USGS Landsat Collection 2 Level-2** via Microsoft Planetary Computer | QA-masked median `lwir11`/surface-temperature product converted using STAC scale/offset metadata |
| Current vegetation | **Copernicus Sentinel-2 Level-2A** via Microsoft Planetary Computer | Cloud-masked median NDVI |
| Current built-up signal | **Copernicus Sentinel-2 Level-2A** | NDBI diagnostic |
| Historical vegetation / built-up signal | **Sentinel-2 Level-2A, Jul–Sep 2021** | Summer-matched NDVI/NDBI baseline for 2021→2026 change |
| Structural built-up share | **ESA WorldCover 2021** | Fraction of valid 10 m pixels classified as class 50 Built-up |
| Population exposure | **WorldPop Global2 API v2, 2026, 100 m** | Estimated population inside each analysis polygon |
| Optional SAR evidence | **Sentinel-1 GRD** via Microsoft Planetary Computer | Same-track VV amplitude-change diagnostic; **not included in the priority score** |
| AOI geometry | **OSM/Nominatim**, custom GeoJSON if supplied, or conservative fallback | Defines the Khalifa City analysis boundary |

### Important interpretation notes

- Landsat LST is **land-surface temperature**, not air temperature.
- WorldCover 2021 is a structural baseline, not a 2026 construction survey.
- WorldPop provides **model-based population estimates**, not official census counts.
- NDVI/NDBI changes are spectral change signals; they are not cadastral construction measurements.
- Sentinel-1 GRD change is diagnostic only because this PoC does not claim calibrated RTC backscatter.
- The final FalconHeat score is **relative to the current Khalifa City AOI**.

---

## Advanced priority model

FalconHeat uses an interpretable five-driver planning index:

```text
H = 0.35T + 0.20B + 0.15V + 0.15P + 0.15C
```

where:

- **T** = relative Landsat surface temperature
- **B** = relative WorldCover built-up share
- **V** = low current Sentinel-2 vegetation
- **P** = log-normalized WorldPop population exposure
- **C** = 2021→2026 urban-change stress derived from vegetation loss and positive NDBI change

All components are min-max normalized **within the current Khalifa City analysis polygons**.

If an optional source is unavailable for a cell, FalconHeat does **not** invent a value. Instead, the missing component's weight is redistributed over the measured components and the effective weights are stored in the output table.

### Explainability

Every cell includes the contribution of each driver in priority points:

- `contrib_temperature`
- `contrib_built_up`
- `contrib_low_vegetation`
- `contrib_population`
- `contrib_urban_change`

The dashboard identifies each cell's top driver and generates a planning recommendation from the actual driver profile.

---

## Khalifa City AOI precision

FalconHeat no longer assumes that a rectangular bounding box equals Khalifa City.

Boundary priority:

1. `data/khalifa_city_boundary.geojson` if the team uploads an organizer/municipal/drawn boundary;
2. OpenStreetMap/Nominatim polygon;
3. a conservative built-in fallback polygon.

Every analysis polygon is **clipped to that AOI**, and every raster statistic is spatially masked to the clipped polygon.

The Streamlit sidebar also allows a custom Khalifa City GeoJSON to be uploaded and applied without editing code.

---

## Urban-change methodology

The dashboard compares:

- **Jul–Sep 2021 Sentinel-2**
- **Jul–Sep 2026 Sentinel-2**

Using the same seasonal window reduces seasonal vegetation bias.

For each clipped Khalifa City polygon FalconHeat calculates:

- NDVI 2021
- NDVI 2026
- ΔNDVI
- NDBI 2021
- NDBI 2026
- ΔNDBI

Urban-change stress is driven only by:

- **vegetation loss**: `max(0, -ΔNDVI)`
- **positive NDBI change**: `max(0, ΔNDBI)`

The app does not label spectral-index change as exact square metres of urban expansion.

---

## Population exposure

FalconHeat calls the official **WorldPop API v2** for each clipped analysis polygon using:

- year: **2026**
- resolution: **100 m**

It stores:

- estimated polygon population;
- polygon area;
- estimated population density.

WorldPop failures do not stop the core EO dashboard and are not replaced with synthetic population values.

---

## Evidence confidence

`data_confidence` is an **evidence-completeness score**, not a statistical confidence interval.

It summarizes:

- current Sentinel-2 cloud/coverage quality;
- historical Sentinel-2 cloud/coverage quality;
- Landsat cloud/coverage quality;
- WorldCover AOI coverage;
- WorldPop availability;
- analysis-polygon geometry coverage.

This gives judges and planners a quick indication of where FalconHeat has the strongest source support.

---

## Scenario Lab

The Scenario Lab lets a user test assumptions such as:

- lower land-surface temperature;
- higher NDVI;
- lower exposed built-up share;
- lower population exposure.

The resulting before/after score is explicitly marked as a **sensitivity test, not a physical forecast**.

This makes FalconHeat useful for comparing intervention ideas without pretending to predict the exact outcome of planting trees or applying cool roofs.

---

## Run locally

Recommended: Python 3.11 or 3.12.

```bash
cd FalconHeat-AI-Self-Explaining

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m streamlit run app.py
```

The first complete refresh can take several minutes because FalconHeat queries current Sentinel-2, historical Sentinel-2, Landsat, WorldCover, WorldPop and optional Sentinel-1 evidence.

Once completed, it caches:

```text
data/processed/khalifa_city_eo.csv
data/processed/khalifa_city_eo_metadata.json
```

Subsequent launches use the cached real-data result until **Refresh all EO data** is clicked.

---

## 813 Challenge Imagery Lab

The **Evidence & Export** tab accepts an organizer-provided 813 GeoTIFF. FalconHeat reports raster dimensions, CRS, bounds, band count and pixel size, and allows an interactive three-band quicklook.

Because the 813 products may be multispectral/hyperspectral/VHR with product-specific band semantics, uploaded 813 bands are **not automatically inserted into the priority score** until their wavelengths/calibration are confirmed. This keeps the competition-native evidence visible without creating unsupported scientific claims.

## Reproducible output

The Evidence & Export tab allows judges/users to download:

- the analyzed CSV;
- the full source/provenance JSON.

The provenance file records actual scene IDs, acquisition dates, cloud metadata, AOI source and optional-layer availability.

---

## Repository structure

The repository follows the **813 Challenge starter structure** supplied by the organizers.  
FalconHeat also keeps the small runtime folders required by the live Streamlit website.

```text
falconheat-khalifa-city/
│
├── README.md
│
├── notebooks/
│   ├── 00_data_exploration_starter.ipynb
│   ├── 01_agriculture_crop_intelligence.ipynb
│   ├── 02_land_use_land_cover_change.ipynb      ← Team 971 Liftoff / FalconHeat
│   ├── 03_air_quality_ghg_plumes.ipynb
│   ├── 04_climate_disasters_fire_flood.ipynb
│   └── 05_ecosystem_health_blue_carbon.ipynb
│
├── docs/
│   ├── spectral_indices_reference.md
│   ├── tanager_data_guide.md
│   └── stac_collection_map.md
│
├── assets/
│   └── images/
│
├── requirements.txt
│
├── app.py                                  ← live FalconHeat Streamlit app
├── src/                                    ← FalconHeat analysis code
└── data/                                   ← published real-EO snapshot/provenance
```

The hackathon submission is **Theme 2: Urban Expansion, Land Use Change & Heat Risk**.  
The main reproducible notebook is `notebooks/02_land_use_land_cover_change.ipynb`.

---

## Deep learning note

The optional `src/eo_deep_learning.py` contains a generic DeepLabV3 technical experiment. Its default torchvision checkpoint is **not an EO-trained land-cover model** and is therefore deliberately separated from the main evidence engine.

FalconHeat's primary dashboard does not depend on generic segmentation classes.

A future competition/research extension should fine-tune an EO segmentation model and report mIoU / class-level validation metrics before using its output as a planning indicator.

---



## Scientific review correction (v4.2)

After generating the real Khalifa City dataset, FalconHeat v4.2 performs an additional interpretation guard on the 2021→2026 Sentinel-2 change component.

In the reviewed run, all analysis polygons had negative `ΔNDBI` and the largest NDVI decrease was small. The earlier relative normalization could make the largest *small* change look disproportionately important.

v4.2 therefore uses a transparent PoC tolerance:

- `ΔNDVI <= -0.02` before vegetation-loss change begins contributing;
- `ΔNDBI >= +0.02` before positive NDBI change begins contributing.

Changes inside `±0.02` remain visible in the Urban Change tab but are treated as **inconclusive for the priority score**.

This tolerance is a conservative PoC interpretation rule, not a universal remote-sensing significance threshold. A final research/operational system should calibrate change thresholds using multi-date composites, reference labels and field/municipal validation.

Most importantly, FalconHeat does not describe negative NDBI change as urban expansion.


## Competition UI polish (v4.1)

The competition build is optimized for laptop/projector presentation:

- executive metrics are arranged in two rows to prevent Streamlit value truncation;
- the dashboard reports **hottest surface anomaly** rather than median anomaly;
- WorldPop output is labelled **estimated residents**, not a measured head count;
- analytical zones appear as `Kxx · near <local reference>` so a FalconHeat cell is never presented as an official municipal sector boundary;
- every High/Very High hotspot receives an automatically generated **Why this area?** explanation based on its two largest model contributions;
- the top-priority polygon receives an executive insight sentence suitable for a live pitch.


## Competition message

FalconHeat's core value is not simply "showing a heat map."

It demonstrates an end-to-end decision workflow:

```text
Real EO + population data
        ↓
Precise AOI masking
        ↓
Current heat + vegetation + built-up land
        ↓
2021→2026 urban-change evidence
        ↓
Population exposure
        ↓
Explainable priority score
        ↓
Driver-specific intervention guidance
        ↓
Scenario testing + reproducible export
```

**FalconHeat — from satellite observations to explainable, climate-resilient urban decisions.**


## Final presentation polish (v4.3)

The v4.3 competition build fixes the remaining visible presentation issues:

- no duplicate `summer-matched` wording;
- no stray raw HTML in non-hotspot queue cards;
- AOI provenance explicitly distinguishes a curated study polygon from an official municipal boundary;
- the executive page displays a data-integrity status line;
- WorldPop is consistently described as estimated residents;
- Scenario Lab wording avoids implying that the 2021 WorldCover class map itself is being physically edited.

The underlying EO and v4.2 conservative change-scoring methodology are unchanged.



## Public competition deployment

Live dashboard: **https://falconheat-khalifa-city.streamlit.app**

The public Streamlit build uses the bundled real-data competition snapshot so judges can interact with the maps, explainability views, exposure analysis and Scenario Lab without triggering a remote EO rebuild.

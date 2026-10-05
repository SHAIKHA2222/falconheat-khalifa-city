# Generated EO cache

On first launch, FalconHeat queries the organizer-approved public datasets through Microsoft Planetary Computer and writes:

- `khalifa_city_eo.csv`
- `khalifa_city_eo_metadata.json`

These files contain the real Khalifa City Earth-observation measurements and exact STAC item metadata used by the dashboard. The repository deliberately does not ship invented fallback values.

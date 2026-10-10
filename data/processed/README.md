# Published competition snapshot

The repository bundles `khalifa_city_eo.csv` and `khalifa_city_eo_metadata.json`.
The deployment marker makes the public app load this snapshot without remote acquisition.
The CSV's derived scores were synchronized with analysis version 4.4; source input values were preserved.

The app recalculates derived scores at startup and exports those results. Provenance records the team's reported source products. Catalog existence and numerical consistency do not independently validate every source-derived value; raw imagery and original population API responses are not bundled.

Use the main notebook for offline reproduction or an opt-in remote rebuild into a separate directory. Do not overwrite the published snapshot without reviewing new results.

# Deploy FalconHeat to Streamlit Community Cloud

This folder is the **public read-only competition snapshot**. The real processed EO
CSV and provenance metadata are bundled so the public website opens immediately.
Visitors can use filters, maps, explainability, Exposure, Urban Change, and the
Scenario Lab, but cannot rebuild the EO data or replace the AOI.

## 1. Create a public GitHub repository

Suggested repository name:

`falconheat-khalifa-city`

Upload the **contents of this FalconHeat folder** to the root of the repository.
`app.py` and `requirements.txt` must be visible at the repository root.

## 2. Deploy

1. Open https://share.streamlit.io
2. Sign in with GitHub.
3. Click **Create app** / **Deploy an app**.
4. Select your `falconheat-khalifa-city` repository.
5. Branch: `main`
6. Main file path: `app.py`
7. Open **Advanced settings** and choose **Python 3.12**.
8. Click **Deploy**.

The final URL will look similar to:

`https://falconheat-khalifa-city.streamlit.app`

## 3. Share

Open the deployed app, click **Share**, then **Copy link**.

## Important

- Keep `data/processed/khalifa_city_eo.csv`.
- Keep `data/processed/khalifa_city_eo_metadata.json`.
- Keep `data/processed/deployment_snapshot.marker`.
- Do not commit `.venv`.
- This deployed build uses a real-data snapshot; it does not generate synthetic values.

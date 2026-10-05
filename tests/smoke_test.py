"""Offline smoke tests for FalconHeat v4.2."""
import pandas as pd
from src.analysis import run_analysis, scenario_score

def main():
    df = pd.DataFrame({
        "zone":["A","B","C"],
        "latitude":[24.4]*3,
        "longitude":[54.58]*3,
        "lst_c":[45,50,55],
        "ndvi":[.12,.20,.30],
        "built_up":[.65,.45,.20],
        "population_2026":[1000,3000,500],
        # Tiny changes should remain visible but not create change priority.
        "ndvi_change":[-.011,0,.004],
        "ndbi_change":[-.029,-.040,-.035],
    })
    result = run_analysis(df)
    assert result["risk_score"].between(0,100).all()
    assert float(result["contrib_urban_change"].abs().max()) == 0.0
    assert int(result["clear_change_flag"].sum()) == 0

    scenario = scenario_score(
        result, 0, lst_delta_c=-2, ndvi_delta=.03, built_delta=-.03
    )
    assert 0 <= scenario["score"] <= 100
    print("FalconHeat v4.2 smoke test passed.")

if __name__=="__main__":
    main()

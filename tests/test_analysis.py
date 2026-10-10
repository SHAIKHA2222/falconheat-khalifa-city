import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from src.analysis import run_analysis, scenario_score

ROOT = Path(__file__).resolve().parents[1]

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.raw = pd.read_csv(ROOT / 'data/processed/khalifa_city_eo.csv')
        self.df = run_analysis(self.raw)

    def test_published_scores_match_recalculation(self):
        a = self.raw.set_index('cell_id').sort_index()
        b = self.df.set_index('cell_id').sort_index()
        np.testing.assert_allclose(a.risk_score, b.risk_score)
        self.assertEqual(b.loc['K10', 'risk_score'], 57.9)
        self.assertFalse(b.clear_change_flag.any())
        self.assertAlmostEqual(b.population_2026.sum(), 97142)
        self.assertAlmostEqual(b.loc[b.risk_level.isin(['High','Very High']), 'population_2026'].sum(), 52781.4)

    def test_contributions_sum_to_display_score(self):
        cols = [c for c in self.df if c.startswith('contrib_')]
        np.testing.assert_allclose(self.df[cols].sum(axis=1).round(1), self.df.risk_score)

    def test_no_intervention_reproduces_every_baseline(self):
        for i, r in self.df.iterrows():
            s = scenario_score(self.df, i)
            self.assertEqual(s['score'], r.risk_score)
            self.assertEqual(s['level'], r.risk_level)
            self.assertLessEqual(scenario_score(self.df, i, lst_delta_c=-2, ndvi_delta=.05, built_delta=-.05, exposure_reduction_pct=10)['score'], r.risk_score)

    def test_missing_optional_values_reweight_without_imputation(self):
        d = self.raw.copy()
        d['population_2026'] = np.nan
        d['ndvi_change'] = np.nan
        r = run_analysis(d)
        self.assertTrue(r.population_norm.isna().all())
        self.assertTrue(r.urban_change_norm.isna().all())
        self.assertTrue(r.risk_score.between(0,100).all())
        self.assertTrue((r.contrib_population == 0).all())

    def test_change_threshold_direction_and_boundary(self):
        d = self.raw.iloc[:4].copy()
        d['ndvi_change'] = [-.02,-.03,0,0]
        d['ndbi_change'] = [0,0,.03,-.1]
        r = run_analysis(d).set_index('cell_id').loc[d.cell_id]
        self.assertEqual(r.clear_change_flag.tolist(), [False,True,True,False])
        self.assertAlmostEqual(r.urban_change_norm.iloc[1], .0625)
        self.assertEqual(r.urban_change_norm.iloc[3], 0)

    def test_invalid_core_values_are_rejected(self):
        for value in [np.inf,np.nan]:
            d=self.raw.copy();d.loc[0,'lst_c']=value
            with self.assertRaises(ValueError):run_analysis(d)
        d=self.raw.copy();d.loc[0,'built_up']=2
        with self.assertRaises(ValueError):run_analysis(d)

    def test_invalid_population_is_missing_not_zero(self):
        d=self.raw.copy();d.loc[0,'population_2026']=-1
        r=run_analysis(d).set_index('cell_id')
        self.assertTrue(pd.isna(r.loc[d.cell_id.iloc[0],'population_norm']))

if __name__ == '__main__':unittest.main()

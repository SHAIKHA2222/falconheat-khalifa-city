import json
import io
from unittest.mock import patch
import pandas as pd
from streamlit.delta_generator import DeltaGenerator
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=45).run()

    def test_dashboard_and_controls(self):
        a=self.app
        self.assertFalse(a.exception)
        self.assertEqual(len(a.tabs),5)
        for layer in ['Surface temperature','Estimated resident exposure','Vegetation change','Priority']:
            a.selectbox[0].select(layer).run()
            self.assertFalse(a.exception)
        a.multiselect[0].set_value([]).run()
        self.assertFalse(a.exception)
        self.assertTrue(any('No polygons match' in x.value for x in a.info))
        a.multiselect[0].set_value(['Low','Moderate','High','Very High']).run()
        a.slider[0].set_value(100).run()
        self.assertFalse(a.exception)
        a.slider[0].set_value(0).run()
        for i in range(1,5):a.slider[i].set_value(0)
        a.run()
        values={m.label:m.value for m in a.metric}
        self.assertEqual(values['Current priority'], values['Scenario priority'])
        self.assertEqual(values['Priority reduction'],'0.0 points')
        # The actual download payloads are generated on every run.
        self.assertEqual(len(a.get('download_button')),2)

    def test_export_payloads(self):
        payloads = {}
        original = DeltaGenerator.download_button
        def capture(self, label, data, **kwargs):
            payloads[label] = data
            return original(self, label, data, **kwargs)
        with patch.object(DeltaGenerator, 'download_button', new=capture):
            a = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=45).run()
        self.assertFalse(a.exception)
        csv = pd.read_csv(io.BytesIO(payloads['⬇ Download analyzed CSV']))
        meta = json.loads(payloads['⬇ Download provenance JSON'])
        self.assertEqual(len(csv),12)
        self.assertEqual(csv.set_index('cell_id').loc['K10','risk_score'],57.9)
        self.assertEqual(meta['analysis_model']['version'],'4.4')
        self.assertAlmostEqual(sum(meta['analysis_model']['nominal_weights'].values()),1)

if __name__=='__main__':unittest.main()

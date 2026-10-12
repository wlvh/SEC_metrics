"""Two real saved annual factories through the shared test-side guard."""
from pathlib import Path
import unittest
from tests.vnext.test_annual_input import independent_inputs
from tests.vnext.processing_dependency_checks import processing_calls,assert_processing_calls
from vnext.ordinary_current_update import _configuration
from vnext.ordinary_saved_result import _ordinary_case
from vnext.deterministic_router import shared_xbrl_parses

ROOT=Path(__file__).resolve().parents[2]


class ProcessingDependencyMaterialTest(unittest.TestCase):
    def test_saved_factories_use_only_declared_processing_modules(self):
        with independent_inputs(),shared_xbrl_parses():
            for metric in ('B01','B04'):
                with self.subTest(metric=metric):
                    configuration=_configuration(ROOT,'enphase_energy',metric)
                    with processing_calls(ROOT) as observed:
                        case=_ordinary_case(ROOT,'enphase_energy',metric)
                    self.assertEqual(case['primary_metric_id'],metric)
                    self.assertTrue(observed)
                    assert_processing_calls(observed,configuration)

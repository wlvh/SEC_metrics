"""Explicit ordinary preparation uses runtime rules and separate raw inputs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vnext import r6_semantic_source as semantic,capacity_semantic_source as capacity,normal_annual_input_v2 as annual


class NativeSourceRuntimePolicyTest(unittest.TestCase):
    def test_explicit_ordinary_uses_runtime_rules_before_raw_source_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            for module,function,next_function in [(semantic,'prepare_d04_semantic_source','prepare_ordinary_going_concern_source'),
                                                   (capacity,'prepare_capacity_semantic_source','prepare_d04_semantic_source'),
                                                   (annual,'prepare_saved_annual_input','prepare_original_input')]:
                with self.subTest(module=module.__name__),patch.object(module,next_function,side_effect=RuntimeError('RAW_SOURCE_REQUIRED')) as read:
                    with self.assertRaisesRegex(RuntimeError,'RAW_SOURCE_REQUIRED'):
                        getattr(module,function)(repo_root=root,company_id='enphase_energy',ordinary_registered=True)
                    self.assertEqual(read.call_args.kwargs['repo_root'],root)
                    read.reset_mock()
                    with self.assertRaises((ValueError,FileNotFoundError)):
                        getattr(module,function)(repo_root=root,company_id='enphase_energy')
                    read.assert_not_called()

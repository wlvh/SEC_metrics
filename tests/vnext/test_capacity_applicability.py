"""Approved B13 scope is distinct from interpreted disclosure absence."""
from pathlib import Path
import json
import socket
import tempfile
import unittest
from unittest.mock import patch

from vnext.capacity_run import _prepare_structural_case, install_inputs, create_run
from vnext.capacity_utilization_source import policy
from vnext.normal_source_authority import ROOT


class CapacityApplicabilityTest(unittest.TestCase):
    def test_applicable_companies_cannot_use_the_structural_branch(self):
        _, approved = policy()
        for company in approved['applicable_company_ids']:
            with self.subTest(company=company), self.assertRaisesRegex(
                    ValueError, 'APPLICABLE_COMPANY_CANNOT_BE_STRUCTURAL'):
                _prepare_structural_case(data_root=ROOT, company_id=company)


class CapacityApplicabilityMaterialTest(unittest.TestCase):
    def test_native_structural_result_rejects_fabricated_disclosure_absence(self):
        from vnext.projector import _load_registry
        from vnext.ordinary_projection import render_ordinary_run
        from vnext.run_store import _mechanically_replay_open_run, RunStoreError
        from vnext.text_results import build_text_result_and_trace
        _, approved = policy()
        company = next(c['company_id'] for c in _load_registry(repo_root=ROOT)
                       if c['company_id'] not in approved['applicable_company_ids'])
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')):
            root = Path(temporary); data, run = root / 'data', root / 'run'
            case = install_inputs(data_root=data, company_id=company)
            created = create_run(data_root=data, run_dir=run, company_id=company)
            rendered = render_ordinary_run(data_root=data, run_dir=run)
            self.assertEqual(created['result']['applicability'], 'N_A_STRUCTURAL')
            self.assertEqual(rendered['row']['status'], 'N_A_STRUCTURAL')
            self.assertEqual(rendered['row']['value'], '')
            self.assertEqual(rendered['evidence'], [])
            self.assertFalse((data / 'config/ordinary_capacity_assessment.json').exists())
            self.assertFalse(case['selection']['disclosure_absence_asserted'])
            result, trace = build_text_result_and_trace(compiled_spec=case['compiled_specs']['B13'],
                target=case['traces']['B13']['calculation_target'],
                reason_code='B13_DEFINED_SCOPE_NO_RELEVANT_DISCLOSURE')
            original = (run / 'records.jsonl').read_bytes()
            records = [r for r in map(json.loads, original.splitlines())
                       if r['record_type'] not in {'METRIC_RESULT', 'EXECUTION_TRACE'}]
            records.extend([trace, result])
            (run / 'records.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
            try:
                with self.assertRaisesRegex(RunStoreError, 'B13_STRUCTURAL_RECORD_SET_CHANGED'):
                    _mechanically_replay_open_run(run_dir=run, repo_root=data, require_complete_results=True)
            finally:
                (run / 'records.jsonl').write_bytes(original)

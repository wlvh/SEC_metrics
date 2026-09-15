"""Numeric Run plumbing with explicit synthetic source/admission test doubles.

This tests the actual quantity reader, Calculator, record graph and projector.
It does not attest a provider execution or a newly admitted SEC source. The
separate complete real-material tests retain responsibility for those gates.
"""
from copy import deepcopy
from pathlib import Path
import json
import socket
import tempfile
import unittest
from unittest.mock import patch

from tests.vnext.test_capacity_utilization_source import quantity_source
from vnext.canonical import content_hash
from vnext.normal_source_authority import ROOT


class CapacityNumericRunTest(unittest.TestCase):
    def test_numeric_run_replays_sources_and_rejects_resigned_false_ratio(self):
        from vnext.capacity_run import prepare_case, create_run
        from vnext.capacity_utilization_source import calculate_source_comparable_pair, calculate_comparable_pair
        from vnext.normal_run_v3 import _install_case_inputs
        from vnext.requirements import load_requirement_snapshot
        from vnext.ordinary_projection import render_ordinary_run
        from vnext.run_store import _mechanically_replay_open_run, RunStoreError
        source, raw = quantity_source('<p>For fiscal year 2025, we produced 80 million widgets worldwide.</p>'
            '<p>For fiscal year 2025, our available annual production capacity was 100 million widgets worldwide.</p>')
        source['source_proofs'] = []
        source['semantic_source_id'] = content_hash(value={k:v for k,v in source.items() if k != 'semantic_source_id'})
        assessment = {'proposed_branch':'COMPARABLE_QUANTITY_PAIR_ASSESSMENT_REQUIRED',
            'assessment_set_id':content_hash(value='explicit synthetic assessment double')}
        registered = {'assessment':assessment, 'mode':'RECORDED_TEST_ONLY',
            'input_record_id':content_hash(value='explicit synthetic registration double')}
        admission = {'source_credit':'RECORDED_TEST_ONLY', 'checkpoint_id':content_hash(value='synthetic admission double')}
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('vnext.capacity_run.prepare_capacity_semantic_source', return_value=source), \
             patch('vnext.capacity_run.load_registered_input', return_value=registered), \
             patch('vnext.capacity_run.verify_ordinary_source_proofs', return_value=admission), \
             patch('vnext.normal_run_v3.verify_ordinary_source_proofs', return_value=admission), \
             patch('vnext.ordinary_projection.prepare_saved_annual_input', return_value=source['prepared_annual_input']):
            base = Path(temporary).resolve(); data, run = base/'data', base/'run'
            requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14')
            _install_case_inputs(data_root=data, source_root=ROOT, company_id=source['company_id'],
                case={'source_proofs':[], 'primary_metric_id':'B13'}, requirement=requirement)
            path = data/source['documents'][0]['raw_blob']['storage_uri']; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(next(iter(raw.values())))
            case = prepare_case(data_root=data, company_id=source['company_id'])
            self.assertEqual(case['kind'], 'STRUCTURED')
            created = create_run(data_root=data, run_dir=run, company_id=source['company_id'])
            self.assertEqual(created['result']['value'], '0.8')
            rendered = render_ordinary_run(data_root=data, run_dir=run)
            self.assertEqual(rendered['row']['value'], '0.8')
            self.assertEqual(rendered['row']['unit'], 'ratio')
            self.assertEqual(len(rendered['evidence']), 2)
            self.assertEqual({e['value_raw'] for e in rendered['evidence']}, {'80 million','100 million'})
            self.assertTrue(all('fiscal year 2025' in e['evidence_quote'] for e in rendered['evidence']))
            self.assertFalse(rendered['receipt']['production_authorized'])
            parsed = calculate_source_comparable_pair(source=source, raw_bytes_by_id=raw)
            production = deepcopy(parsed['source_quantity_proofs']['ACTUAL_PRODUCTION'])
            production['value'] = '81000000'
            false = calculate_comparable_pair(target=parsed['target'], production=production,
                capacity=parsed['source_quantity_proofs']['AVAILABLE_CAPACITY'])
            records_path = run/'records.jsonl'; original = records_path.read_bytes()
            records = [r for r in map(json.loads, original.splitlines()) if r['record_type'] not in
                       {'METRIC_RESULT','EXECUTION_TRACE','VERIFIED_OBSERVATION'}]
            records.extend([*false['observations'],false['trace'],false['result']])
            records_path.write_text(''.join(json.dumps(r)+'\n' for r in records))
            try:
                with self.assertRaisesRegex(RunStoreError, 'B13_NUMERIC_RECORD_SET_CHANGED'):
                    _mechanically_replay_open_run(run_dir=run, repo_root=data, require_complete_results=True)
            finally:
                records_path.write_bytes(original)

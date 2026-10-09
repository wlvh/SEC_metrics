"""Re-signed numbers and absence claims cannot replace native scoped gaps."""
import json
import os
from decimal import Decimal
from pathlib import Path
import shutil
import unittest

from vnext.calculator import _result_and_trace
from vnext.records import validate_record
from vnext.run_store import _mechanically_replay_open_run
from vnext.specs import compile_spec_file


@unittest.skipUnless(os.environ.get('SPECIAL_DEBT_NATIVE_BATCH'), 'Requires completed special-scope native batch')
class SpecialDebtRunMaterialTest(unittest.TestCase):
    def test_scoped_missing_proof_cannot_be_replaced_by_a_ratio_or_absence(self):
        base = Path(os.environ['SPECIAL_DEBT_NATIVE_BATCH']).resolve()
        out = Path(os.environ['SPECIAL_DEBT_ATTACK_ROOT']).resolve()
        self.assertFalse(out.exists()); out.mkdir()
        summary = json.loads((base / 'summary.json').read_text())
        self.assertEqual(len(summary['coordinates']), 2)
        checked = []
        for c in summary['coordinates']:
            self.assertEqual(c['status'], 'WITHHELD_CANDIDATE')
            self.assertEqual(c['run_status'], 'OPEN')
            self.assertEqual(c['public_row_status'], 'CANDIDATE_ROW_PREPARED')
            self.assertIsNone(c['result']['value']); self.assertEqual(c['result']['publication'], 'WITHHELD')
            company = c['company_id']; run = base / c['run_path']; data = base / c['data_path']
            original = [json.loads(line) for line in (run / 'records.jsonl').read_text().splitlines()]
            trace = next(r for r in original if r['record_type'] == 'EXECUTION_TRACE')
            spec = compile_spec_file(path=data / 'catalog/r5/B06_new_source_v2.md', dependency_specs={})
            for name, quality, publication, value, reason in [
                ('fabricated_complete_ratio', 'EXACT', 'PUBLISHED', '1', 'PASS'),
                ('unproven_source_absence', 'NONE', 'WITHHELD', None, 'NOT_AVAILABLE_SEC')]:
                dest = out / company / name; shutil.copytree(run, dest)
                result, new_trace = _result_and_trace(compiled_spec=spec, target=trace['calculation_target'],
                    applicability='APPLICABLE', quality=quality, publication=publication, reason_code=reason,
                    value=Decimal(value) if value is not None else None, result_unit='ratio' if value else None,
                    trace_steps=[{'event': 'WITHHELD', 'reason_code': reason}], input_ids=[])
                records = [r for r in original if r['record_type'] not in {'METRIC_RESULT', 'EXECUTION_TRACE'}]
                records.extend([new_trace, result])
                for record in records:
                    validate_record(record=record)
                (dest / 'records.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in records))
                with self.assertRaisesRegex(ValueError, 'COMPLETE_COMPUTATION_GRAPH_CHANGED'):
                    _mechanically_replay_open_run(run_dir=dest, repo_root=data, require_complete_results=True)
                checked.append({'company': company, 'case': name, 'result': 'REJECTED', 'records_reidentified_and_valid': True})
        (out / 'summary.json').write_text(json.dumps({'status': 'PASS', 'checks': checked, 'new_calls': [0, 0, 0]}, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()

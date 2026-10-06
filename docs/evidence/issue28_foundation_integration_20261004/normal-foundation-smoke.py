"""Saved-source positive Run/update checks on the isolated main candidate.

Uses the original installed Marriott SEC inputs read-only. No model/network,
freeze, publication or source acquisition; outputs are private regression data.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import time
import traceback
from unittest.mock import patch

from vnext import normal_run_v3 as normal, ordinary_update_cycle as update
from vnext.run_store import RunStoreError
from vnext.canonical import strict_json_file
from vnext.ordinary_projection import render_ordinary_run
from vnext.requirements import load_requirement_snapshot
from vnext.requirement_profile_v1 import validate_execution_authority
from vnext.ordinary_processing_source import current_processing_source

HERE = Path(__file__).resolve().parent
SOURCE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/'
              'native-candidate-results-20260922/marriott_international/data')
OUTPUT = Path(os.environ['FOUNDATION_SMOKE_OUTPUT'])


def identity(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def main():
    if OUTPUT.exists():
        raise ValueError('Fresh private test output required')
    OUTPUT.mkdir(parents=True)
    start = time.monotonic()
    before = identity(SOURCE)
    result = {'code_root':str(normal.ROOT), 'source_root':str(SOURCE),
              'output_root':str(OUTPUT), 'source_scope':'Original saved FY2025, no online discovery',
              'calls':[0,0,0], 'production_authorized':False, 'cases':[]}
    try:
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')), \
             patch('sec_http.urlopen', side_effect=AssertionError('HTTP forbidden')):
            for name in ('issue_28_v13','issue_28_v14'):
                requirement = load_requirement_snapshot(snapshot_dir=normal.ROOT/'requirements'/name)
                validate_execution_authority(repo_root=normal.ROOT, requirement=requirement)
                result.setdefault('requirements', {})[name] = requirement['requirement_closure_hash']
            requirement = load_requirement_snapshot(snapshot_dir=normal.ROOT/'requirements/issue_28_v14')
            # The existing explicit adapter makes a current-rule copy. The old
            # installed package must not be relabelled or mutated in place.
            processing = current_processing_source(acquisition_root=SOURCE,
                output_parent=OUTPUT/'processing-input', requirement=requirement)
            current_source = processing['data_root']
            result['processing_source'] = {k:str(v) if isinstance(v,Path) else v
                                           for k,v in processing.items()}
            first = update.run_once(state_root=OUTPUT/'state', source_root=current_source,
                source_identity_root=SOURCE,
                company_id='marriott_international', metric_ids=['B01'])
            result['cases'].append({'case':'saved-source-positive-update','outcome':first})
            if first['status'] != 'CANDIDATE_READY':
                raise AssertionError('Initial update failed: '+first['status'])
            current = strict_json_file(path=OUTPUT/'state/current.json')
            attempt = OUTPUT/'state/attempts'/current['successful_attempt']
            rows_before = (attempt/'rows/B01/metrics_matrix.csv').read_bytes()
            second = update.run_once(state_root=OUTPUT/'state', source_root=current_source,
                source_identity_root=SOURCE,
                company_id='marriott_international', metric_ids=['B01'])
            result['cases'].append({'case':'unchanged-input-reuses-existing-run','outcome':second})
            assert second['status'] == 'NO_SOURCE_CONTENT_CHANGE'
            assert second['successful_attempt'] == first['successful_attempt']
            rendered = render_ordinary_run(data_root=attempt/'data', run_dir=attempt/'runs/B01')
            assert rendered['files']['metrics_matrix.csv'] == rows_before
            result['row'] = rendered['row']
            result['cases'].append({'case':'native-replay-and-public-row-byte-comparison','status':'PASS'})
            # Tamper only a private installed copy, not the original source.
            record = attempt/'runs/B01/manifest.json'
            original = record.read_bytes()
            changed = json.loads(original)
            changed['target_period']['fiscal_year'] += 1
            record.write_text(json.dumps(changed))
            try:
                render_ordinary_run(data_root=attempt/'data', run_dir=attempt/'runs/B01')
            except (ValueError, RunStoreError) as error:
                result['cases'].append({'case':'changed-run-period-is-rejected','status':'PASS','reason':str(error)})
            else:
                raise AssertionError('Changed Run period was accepted')
            finally:
                record.write_bytes(original)
            with update._locked(OUTPUT/'state'):
                try:
                    update.run_once(state_root=OUTPUT/'state', source_root=current_source,
                        source_identity_root=SOURCE,
                        company_id='marriott_international', metric_ids=['B01'])
                except ValueError as error:
                    assert 'UPDATE_ALREADY_RUNNING' in str(error)
                    result['cases'].append({'case':'concurrent-update-is-rejected','status':'PASS'})
                else:
                    raise AssertionError('Concurrent update was accepted')
        assert identity(SOURCE) == before
        result['original_source_bytes_unchanged'] = True
        result['status'] = 'PASS_LIMITED_FOUNDATION'
    except Exception as error:
        result.update(status='FAIL', error=str(error), traceback=traceback.format_exc(),
                      original_source_bytes_unchanged=identity(SOURCE)==before)
    result['seconds'] = time.monotonic()-start
    (HERE/'normal-foundation-smoke-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','traceback')},indent=2))
    return 0 if result['status'] == 'PASS_LIMITED_FOUNDATION' else 1


if __name__ == '__main__':
    raise SystemExit(main())

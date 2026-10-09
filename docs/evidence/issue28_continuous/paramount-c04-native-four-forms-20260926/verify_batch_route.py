"""Run one saved-source C04 batch coordinate with all network sockets blocked."""
import json
from pathlib import Path
import socket
from unittest.mock import patch

from vnext.c04_registration_successor import EVENT_FORMS
from vnext.canonical import sha256_file, strict_json_file
from vnext.normal_source_authority import ROOT


HERE = Path(__file__).resolve().parent
SOURCE_ROOT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
OUTPUT_ROOT = Path('/private/tmp/issue28-c04-batch-20260926-01')


def main():
    from tools.vnext_normal_candidate import main as batch
    assert not OUTPUT_ROOT.exists()
    with patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')):
        exit_code = batch(['--output-root', str(OUTPUT_ROOT),
            '--source-root', str(SOURCE_ROOT),
            '--company', 'paramount_skydance_paramount_global',
            '--metric', 'C04'])
    request = strict_json_file(path=OUTPUT_ROOT/'request.json')
    report = strict_json_file(path=OUTPUT_ROOT/'summary.json')
    assert request['c04_event_forms'] == EVENT_FORMS
    assert report['requested_coordinate_count'] == 1
    row, = report['coordinates']
    assert exit_code == 2 and report['status'] == 'COMPLETED_WITH_GAPS'
    assert row['status'] == 'WITHHELD_CANDIDATE'
    assert row['result']['value'] is None
    assert row['result']['reason_code'] == 'C04_COMPARABLE_AUDITOR_FACTS_MISSING'
    prior = strict_json_file(path=HERE/'summary-shard-repair.json')
    assert row['result']['result_id'] == prior['result_id']
    hashes = {name: sha256_file(path=OUTPUT_ROOT/'rows'/row['company_id']/'C04'/name)
              for name in prior['public_row_sha256']}
    assert hashes == prior['public_row_sha256']
    result = {'status': 'PASS_SAVED_C04_BATCH_AUTO_FOUR_FORM_ROUTE',
        'code_root': str(ROOT), 'source_root': str(SOURCE_ROOT),
        'output_root': str(OUTPUT_ROOT), 'batch_exit_code': exit_code,
        'run_id': row['run_id'], 'result_id': row['result']['result_id'],
        'result_value': None, 'reason_code': row['result']['reason_code'],
        'public_row_sha256': hashes, 'new_calls': [0, 0, 0],
        'production_authorized': False,
        'boundary': 'One saved-source candidate coordinate, not automatic new-source acquisition or full C04 business resolution.'}
    (HERE/'batch-route-summary.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

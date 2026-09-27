"""Read the actual private C04 Run with frozen legacy semantic exports closed.

This is one route's private dependency rehearsal, not a production switch or
proof of the entire 390-coordinate graph.
"""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))

import sec_pipeline as legacy
from vnext import c04_update_cycle as c04
from vnext.canonical import strict_json_file


LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
STATE = LEDGER/'private-c04-salesforce-fy2026-20260927'
INVENTORY = ROOT/'requirements/issue_15_v1/legacy_semantic_producer_inventory.json'
ACTIVE = ROOT/'outputs/active_publication.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    inventory = strict_json_file(path=INVENTORY)
    semantic = [row for row in inventory['producers']
                if row['kind'] == 'SEMANTIC_PRODUCER']
    names = [row['producer_id'].split('::')[1] for row in semantic]
    metric_ids = set(strict_json_file(path=ROOT/'config/source_strategy_registry.json')['metrics'])
    assert len(names) == len(set(names)) == 116 and len(metric_ids) == 39
    assert set(metric for row in semantic
               for metric in row['covered_metric_ids']) == metric_ids
    assert all(callable(getattr(legacy, name)) for name in names)

    state = strict_json_file(path=STATE/'current.json')
    terminal = c04.cycle._terminal(STATE, state['successful_attempt'])
    config = c04.cycle._read(STATE/'configuration.json')
    work = STATE/'attempts'/state['successful_attempt']
    manifest = strict_json_file(path=work/'runs/C04/manifest.json')
    rows = work/'rows/C04/metrics_matrix.csv'
    evidence = work/'rows/C04/metric_evidence.csv'
    before = {str(path): sha(path) for path in
              (ACTIVE, LEDGER/'claims.jsonl', rows, evidence,
               work/'runs/C04/manifest.json')}
    replacements = {name: legacy.retired_legacy_entrypoint(producer=name)
                    for name in names}
    with patch.multiple(legacy, **replacements), \
         patch.object(legacy, 'MIGRATED_VNEXT_METRIC_IDS', frozenset(metric_ids)), \
         patch.object(socket.socket, 'connect',
                      side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
                      side_effect=AssertionError('DNS_FORBIDDEN')), \
         patch('sec_http.urlopen',
               side_effect=AssertionError('HTTP_FORBIDDEN')), \
         patch.object(subprocess, 'Popen',
                      side_effect=AssertionError('SUBPROCESS_FORBIDDEN')):
        try:
            getattr(legacy, names[0])()
        except legacy.LegacyPathStillActiveError:
            blocked_control = True
        else:
            raise AssertionError('LEGACY_SEMANTIC_PATCH_NOT_EFFECTIVE')
        result = c04._verify_candidate(STATE, terminal, config)['C04']
    after = {str(path): sha(path) for path in
             (ACTIVE, LEDGER/'claims.jsonl', rows, evidence,
              work/'runs/C04/manifest.json')}
    assert before == after and blocked_control
    assert result['publication'] == 'PUBLISHED' and result['value'] == '0'
    assert result['result_id'] == terminal['metrics']['C04']['result_id']
    assert manifest['run_id'].startswith('run:ordinary-integrated:')
    return {'record_type': 'ISSUE28_C04_PRIVATE_LEGACY_DISABLED_REPLAY',
        'status': 'PASS_SINGLE_C04_NATIVE_ROUTE_WITH_LEGACY_EXPORTS_DISABLED',
        'company_id': 'salesforce', 'metric_id': 'C04',
        'fiscal_year': manifest['target_period']['fiscal_year'],
        'result_id': result['result_id'], 'run_id': manifest['run_id'],
        'legacy_semantic_exports_patched': len(names),
        'legacy_write_guard_metric_count': len(metric_ids),
        'blocked_control': blocked_control,
        'active_and_private_run_bytes_unchanged': True,
        'old_entrances_actually_retired': False,
        'complete_390_graph_proven': False,
        'network_and_subprocess_forbidden': True,
        'new_calls': [0, 0, 0], 'production_authorized': False}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))

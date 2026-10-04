"""Finite saved-source lookup and independent-process byte replay; no model."""
import argparse
import json
import socket
import subprocess
import time
from pathlib import Path

from vnext.canonical import sha256_bytes, sha256_file
from vnext.d03_context_requests import resolve_context_requests, replay_context_packet
from vnext.native_unit_index import evidence_json_bytes
from sec_http import write_immutable_bytes

STATE = Path('/Users/lyuhongwang/.local/state/sec_metrics')
BASE = STATE/'issue28-development-evidence'
OUT = BASE/'d03-literal-context-20261004'
HERE = Path(__file__).parent
SAMPLES = [
    ('marriott', BASE/'d03-complete-six-responses-20261004/source.json',
     '5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b',
     'sha256:3345ce064f9231ae17b6b0133c01f16d4bc21ed1866bd7c9e1bf22fa7760d5b9',
     {'kind': 'NATIVE_FACT', 'source_index': 418},
     [{'kind': 'XML_ELEMENT_ID', 'element_id': 'f-408-1'},
      {'kind': 'XML_ELEMENT_ID', 'element_id': 'f-408-2'}]),
    ('jpm', BASE/'d03-jpm-positive-20261004/source.json',
     '11189144bf0bff60c8995086f9fb2bfa253a38a1206d557a059b9c771f8486a9',
     'sha256:622b0eebd9155bdacb77f07779b6e5046a566330559e2ae97a527c65b1d1a8fa',
     {'kind': 'VISIBLE_BLOCK', 'source_index': 10172},
     [{'kind': 'VISIBLE_BLOCK_RANGE', 'first': 10172, 'last': 10175}]),
]


def blocked(*args, **kwargs):
    raise AssertionError('offline check attempted network/subprocess')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--read', action='store_true')
    parser.add_argument('--namespace-fix', action='store_true')
    args = parser.parse_args()
    # Both phases prohibit sockets; cold replay additionally prohibits child processes.
    socket.socket = blocked
    subprocess.Popen = blocked
    started = time.monotonic()
    ledger = STATE/'issue28-2026-09-13/claims.jsonl'
    before = sha256_file(path=ledger)
    results = []
    digest_name = 'namespace-fix-external-digests.json' if args.namespace_fix else 'external-digests.json'
    manifest = json.loads((OUT/digest_name).read_text()) if args.read else {}
    samples = SAMPLES
    if args.namespace_fix:
        _, path, digest, owner, anchor, _ = SAMPLES[0]
        samples = [('marriott-fact-dependencies', path, digest, owner, anchor,
                    [{'kind': 'XML_ELEMENT_ID', 'element_id': 'f-408'}])]
    for name, source_path, digest, owner, anchor, targets in samples:
        source_raw = source_path.read_bytes()
        assert sha256_bytes(content=source_raw) == digest
        source = json.loads(source_raw)
        requests = [{'anchor': {'unit_id': owner, **anchor}, 'target': t} for t in targets]
        packet_path = OUT/(name+'-context.json')
        if args.read:
            packet = json.loads(packet_path.read_text())
            replayed = replay_context_packet(source=source, packet=packet,
                expected_source_sha256=digest, expected_packet_sha256=manifest[name]['packet_sha256'])
            assert replayed == packet
        else:
            packet = resolve_context_requests(source=source, expected_source_sha256=digest,
                responsibility_unit_ids=[owner], requests=requests)
            raw = evidence_json_bytes(packet)
            write_immutable_bytes(path=packet_path, content=raw)
            manifest[name] = {'source_path': str(source_path), 'source_sha256': digest,
                             'packet_sha256': sha256_bytes(content=raw), 'packet_path': str(packet_path)}
        assert all(row['status'] == 'LOCATED' for row in packet['rows'])
        assert not packet['semantic_acceptance'] and not packet['company_result_created']
        assert packet['responsibility_unit_ids'] == [owner]
        results.append({'sample': name, 'source_sha256': digest, 'context_rows': len(packet['rows']),
                        'context_bytes': packet['context_bytes'], 'packet_sha256': manifest[name]['packet_sha256'],
                        'lookup_or_replay': 'PASS_LITERAL_ONLY'})
    if not args.read:
        write_immutable_bytes(path=OUT/digest_name, content=evidence_json_bytes(manifest))
    assert sha256_file(path=ledger) == before
    report = {'phase': 'cold_read' if args.read else 'save', 'results': results,
        'seconds': format(time.monotonic()-started, '.3f'), 'ledger_sha256': before,
        'ledger_unchanged': True, 'network_and_subprocess_forbidden': True,
        'source_acquisition_reauthenticated': False, 'semantic_acceptance': False,
        'complete_company_ready': False, 'business_calls': [0, 0, 0]}
    report_name = 'actual-cold.json' if args.read else 'actual-save.json'
    if args.namespace_fix:
        report_name = 'namespace-fix-' + report_name
    (HERE/report_name).write_bytes(evidence_json_bytes(report))
    print(json.dumps(report))


if __name__ == '__main__':
    main()

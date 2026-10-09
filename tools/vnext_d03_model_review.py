#!/usr/bin/env python3
"""Save/read authenticated D03 development proposals; never execute a model."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from git_workspace import first_symlink_in_path
from sec_http import write_immutable_bytes
from vnext.canonical import strict_json_loads
from vnext.d03_model_processing import (build_development_company_assessment,
    read_development_company_assessment)
from vnext.d03_recorded_response_store import _root


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def save(*, manifest_path, data_root, output_root):
    """Reuse exact immutable bytes after full validation; records are last."""
    root = _root(output_root)
    manifest_path = Path(manifest_path)
    raw_manifest = manifest_path.read_bytes()
    manifest = strict_json_loads(text=raw_manifest.decode('utf-8'))
    _need(type(manifest) is dict and set(manifest) == {
        'company_id', 'source_sha256', 'requests'}
        and type(manifest['requests']) is list and manifest['requests'],
        'D03_DEVELOPMENT_INPUT_MANIFEST_INVALID')
    packets = []
    for row in manifest['requests']:
        _need(type(row) is dict and set(row) == {
            'request_path', 'response_path', 'request_sha256', 'response_sha256'},
            'D03_DEVELOPMENT_INPUT_ROW_INVALID')
        packets.append({'request_body': (manifest_path.parent/row['request_path']).read_bytes(),
            'response_body': (manifest_path.parent/row['response_path']).read_bytes(),
            'expected_request_sha256': row['request_sha256'],
            'expected_response_sha256': row['response_sha256']})
    out = build_development_company_assessment(data_root=data_root,
        company_id=manifest['company_id'], packets=packets,
        expected_source_sha256=manifest['source_sha256'])
    payloads = {'development-input.json': raw_manifest,
        'processing/d03/metadata.json': _json(out['processing']),
        'review-context.json': out['review_context_bytes'],
        'review.md': out['rendered_review_bytes']}
    for i, packet in enumerate(packets):
        payloads['wires/'+str(i)+'/request-body.bin'] = packet['request_body']
        payloads['wires/'+str(i)+'/response.bin'] = packet['response_body']
    # A partial save never exposes the final record set. Existing identical
    # bytes are retained on resume; any conflict refuses without overwriting.
    payloads['records.jsonl'] = b''.join(_json(record)+b'\n' for record in out['records'])
    for name, content in payloads.items():
        target = root/name
        _need(first_symlink_in_path(path=target) is None,
              'D03_DEVELOPMENT_OUTPUT_ALIAS_FORBIDDEN')
        write_immutable_bytes(path=target, content=content)
    return out, manifest['company_id']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    create = sub.add_parser('save')
    create.add_argument('--manifest', required=True, type=Path)
    create.add_argument('--data-root', required=True, type=Path)
    create.add_argument('--output-root', required=True, type=Path)
    read = sub.add_parser('read')
    read.add_argument('--data-root', required=True, type=Path)
    read.add_argument('--output-root', required=True, type=Path)
    read.add_argument('--company', required=True)
    read.add_argument('--candidate-hash', required=True)
    read.add_argument('--review-unit-hash', required=True)
    args = parser.parse_args(argv)
    if args.action == 'save':
        out, company = save(manifest_path=args.manifest, data_root=args.data_root,
                            output_root=args.output_root)
    else:
        root = _root(args.output_root)
        for path in root.rglob('*'):
            _need(not path.is_symlink(), 'D03_DEVELOPMENT_OUTPUT_ALIAS_FORBIDDEN')
        out = read_development_company_assessment(directory=root, data_root=args.data_root,
            company_id=args.company, expected_candidate_hash=args.candidate_hash,
            expected_review_unit_hash=args.review_unit_hash)
        company = args.company
    print(json.dumps({'company_id': company, 'status': out['records'][3]['status'],
        'candidate_hash': out['records'][1]['candidate_hash'],
        'review_unit_hash': out['records'][3]['review_unit_hash'],
        'request_count': len(out['processing']['rows']),
        'native_result_created': out['native_result_created'],
        'native_run_created': out['native_run_created'],
        'provider_attempt_created': out['provider_attempt_created'],
        'calls': [0, 0, 0], 'production_authorized': False}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

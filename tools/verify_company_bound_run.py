#!/usr/bin/env python3
"""Replay a real bound Run and mutate only its actual raw/header locators.

Run in an isolated test directory; it never edits the source Run or checkout.
The runtime argument must select the exact fixed runtime that created the Run.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-root', 'data-root', 'run-dir', 'trust-root', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--deny-read', action='append', type=Path, default=[])
    args = parser.parse_args()
    sys.path[:0] = [str(args.runtime_root/'scripts'), str(args.runtime_root)]
    os.environ['SEC_METRICS_SOURCE_TRUST_ROOT'] = str(args.trust_root)
    from vnext.canonical import strict_json_file, sha256_file
    from vnext.run_store import load_frozen_run, _mechanically_replay_open_run
    from vnext.company_handoff import external
    output = external(args.out)
    if output.exists():
        raise ValueError('PROBE_OUTPUT_EXISTS')
    output.mkdir(parents=True)
    def guard(event, values):
        if event != 'open' or not isinstance(values[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(values[0])).resolve()
        if any(path == denied or denied in path.parents for denied in args.deny_read):
            raise ValueError('PROBE_FORBIDDEN_READ:'+str(path))
    sys.addaudithook(guard)
    start = time.monotonic()
    def replay(run, data):
        manifest = strict_json_file(path=run/'manifest.json')
        if manifest['status'] == 'FROZEN':
            return load_frozen_run(run_dir=run, repo_root=data)
        if manifest['status'] == 'OPEN':
            return _mechanically_replay_open_run(run_dir=run, repo_root=data,
                                                 require_complete_results=True)
        raise ValueError('PROBE_RUN_STATE_UNSUPPORTED')
    replay(args.run_dir, args.data_root)
    baseline_seconds = time.monotonic()-start
    # Locate the bytes from this Run's own SourceReference/RawBlob records.
    # This works for ordinary and historical Runs without selecting an
    # unconsumed working copy or requiring a particular binding directory.
    from vnext.canonical import strict_json_loads
    from vnext.batch_workflow import validate_request_attempt_binding
    records = [strict_json_loads(text=line) for line in
               (args.run_dir/'records.jsonl').read_text().splitlines()]
    blobs = {r['raw_asset_id']: r for r in records if r['record_type'] == 'RAW_BLOB'}
    source = next(r for r in records if r['record_type'] == 'SOURCE_REFERENCE'
                  and r['raw_asset_id'] in blobs)
    proof = validate_request_attempt_binding(repo_root=args.data_root,
        source_url=source['source_url'], content_sha256=source['raw_asset_id'][7:],
        accession=source['accession'], document_name=source['document_name'],
        request_attempt_id=source['request_attempt_id'], require_immutable=True)
    if proof['request_repo_relative_path'] != blobs[source['raw_asset_id']]['storage_uri']:
        raise ValueError('PROBE_RUN_RAW_LOCATOR_DIFFERS')
    probes = []
    for field in ('request_repo_relative_path', 'request_headers_repo_relative_path'):
        sandbox = output/field
        shutil.copytree(args.data_root, sandbox/'data')
        shutil.copytree(args.run_dir, sandbox/'run')
        target = sandbox/'data'/proof[field]
        before = sha256_file(path=target)
        target.write_bytes(target.read_bytes()+b'\nBOUND_RUN_NEGATIVE_PROBE\n')
        start = time.monotonic()
        try:
            replay(sandbox/'run', sandbox/'data')
        except Exception as error:
            result = {'field': field, 'path': proof[field], 'before_sha256': before,
                      'status': 'REJECTED', 'error_type': type(error).__name__,
                      'reason': str(error), 'seconds': time.monotonic()-start}
        else:
            raise AssertionError('Bound Run mutation was accepted:'+proof[field])
        probes.append(result)
    report = {'status': 'PASSED', 'positive_seconds': baseline_seconds,
              'source_request_attempt_id': proof['request_attempt_id'],
              'source_reference_id': source['source_reference_id'],
              'negative_probes': probes, 'uid': os.getuid(),
              'denied_read_roots': [str(p) for p in args.deny_read],
              'new_business_calls': [0, 0, 0], 'production_authorized': False}
    (output/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

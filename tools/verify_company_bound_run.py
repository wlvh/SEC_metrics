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
        path = Path(os.fsdecode(values[0])).absolute()
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
    bindings = list((args.data_root/'ordinary_integrated_bindings').glob('*.json'))
    if len(bindings) != 1:
        raise ValueError('PROBE_EXACTLY_ONE_BOUND_INPUT_REQUIRED')
    binding = strict_json_file(path=bindings[0])
    proof = next(p for p in binding['input_binding']['source_proofs']
                 if p['request_locator_kind'] == 'IMMUTABLE_ATTEMPT')
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
              'negative_probes': probes, 'uid': os.getuid(),
              'denied_read_roots': [str(p) for p in args.deny_read],
              'new_business_calls': [0, 0, 0], 'production_authorized': False}
    (output/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

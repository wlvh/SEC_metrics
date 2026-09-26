#!/usr/bin/env python3
"""Run one finite ordinary source refresh and update; no scheduling or publication."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sec_http import write_immutable_bytes
from git_workspace import first_symlink_in_path
from vnext.continuous_sec_acquisition import live_sec_session
from vnext.ordinary_refresh_cycle import refresh_and_process


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--company', action='append', help='Configured company; default all ten')
    parser.add_argument('--metric', action='append', help='Metric id; default the full configured scope')
    parser.add_argument('--state-root', required=True, type=Path, help='Persistent external ordinary update history')
    parser.add_argument('--max-sec-requests', required=True, type=int, help='Finite SEC limit for this invocation, within the cumulative allowance')
    parser.add_argument('--max-provider-requests', default=0, type=int, help='Finite new native request limit; default 0, within the same cumulative allowance')
    parser.add_argument('--output', required=True, type=Path, help='New external report file')
    args = parser.parse_args(argv)
    output = args.output
    if (not output.is_absolute() or first_symlink_in_path(path=output) is not None
            or output.exists() or ROOT == output or ROOT in output.parents
            or any((p / 'outputs/active_publication.json').exists() for p in output.parents)):
        parser.error('Output must be a new unaliased external report file')
    result = refresh_and_process(session=live_sec_session(), state_root=args.state_root,
        company_ids=args.company, metric_ids=args.metric, max_sec_requests=args.max_sec_requests,
        max_provider_requests=args.max_provider_requests, c04_successor=True)
    write_immutable_bytes(path=output, content=(json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps({'status': result['status'], 'calls': result['calls'], 'output': str(output)}, ensure_ascii=False))
    return 0 if result['status'] == 'UPDATES_READY' else 2


if __name__ == '__main__':
    raise SystemExit(main())

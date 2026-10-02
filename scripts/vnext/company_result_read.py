"""Replay worker launched with exactly one native Run's fixed program tree."""
import base64
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch


def main():
    runtime, work, metric, layout = sys.argv[1:]
    runtime = Path(runtime); work = Path(work)
    from company_worker_guard import install_worker_guards
    install_worker_guards(runtime)
    sys.path[:0] = [str(runtime), str(runtime/'scripts')]
    from vnext.canonical import strict_json_file
    from vnext.requirements import load_requirement_snapshot
    manifest = strict_json_file(path=work/'runs'/metric/'manifest.json')
    from vnext.requirement_profile_v1 import validate_execution_authority
    requirement = load_requirement_snapshot(snapshot_dir=runtime/'requirements'/manifest['requirement_id'])
    if requirement['requirement_closure_hash'] != manifest['requirement_closure_hash']:
        raise ValueError('COMPANY_RESULT_RUNTIME_IDENTITY_CHANGED')
    validate_execution_authority(repo_root=runtime, requirement=requirement)
    with patch.object(socket.socket, 'connect', side_effect=ValueError('COMPANY_RESULT_NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo', side_effect=ValueError('COMPANY_RESULT_DNS_FORBIDDEN')):
        if layout == 'historical':
            from vnext.historical_projection import render_historical_run
            from vnext.normal_history_plan import checkpoint_replayed_once
            from vnext.publication import _csv_bytes, METRIC_FIELDS, EVIDENCE_FIELDS
            with checkpoint_replayed_once():
                rendered = render_historical_run(data_root=work/'data', run_dir=work/'runs'/metric,
                                                frozen=manifest['status'] == 'FROZEN')
            files = {'metrics_matrix.csv': _csv_bytes(rows=[rendered['row']], fieldnames=METRIC_FIELDS),
                     'metric_evidence.csv': _csv_bytes(rows=rendered['evidence'], fieldnames=EVIDENCE_FIELDS)}
        else:
            from vnext.ordinary_projection import render_ordinary_run
            rendered = render_ordinary_run(data_root=work/'data', run_dir=work/'runs'/metric,
                                          frozen=manifest['status'] == 'FROZEN')
            files = rendered['files']
    print(json.dumps({name: base64.b64encode(raw).decode('ascii') for name, raw in files.items()}))


if __name__ == '__main__':
    main()

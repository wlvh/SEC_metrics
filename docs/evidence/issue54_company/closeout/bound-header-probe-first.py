"""Real Run-bound header change after a successful state-keyed replay."""
import json, os, shutil, sys, time
from pathlib import Path
runtime, state, trust, output = map(Path, sys.argv[1:])
sys.path[:0] = [str(runtime), str(runtime/'scripts')]
os.environ['SEC_METRICS_SOURCE_TRUST_ROOT'] = str(trust)
from vnext.canonical import strict_json_file, strict_json_loads, sha256_file
from vnext.company_worker_guard import install_worker_guards
from vnext.company_historical_compute import historical_compute_scope
from vnext.historical_projection import render_historical_run
from vnext.batch_workflow import validate_request_attempt_binding
pointer = state/'updates/historical/2025-12-31/C01/current.json'
saved = strict_json_file(path=pointer)
original = Path(saved['candidate']['rows_root']).parent
sealed = {str(p): sha256_file(path=p) for p in [pointer, *sorted((original/'runs').rglob('*')), *sorted((original/'rows').rglob('*'))] if p.is_file()}
assert not output.exists()
output.mkdir()
work = output/'work'
shutil.copytree(original, work)
records = [strict_json_loads(text=line) for line in (work/'runs/C01/records.jsonl').read_text().splitlines()]
blobs = {r['raw_asset_id']: r for r in records if r['record_type'] == 'RAW_BLOB'}
source = next(r for r in records if r['record_type'] == 'SOURCE_REFERENCE' and r['raw_asset_id'] in blobs)
proof = validate_request_attempt_binding(repo_root=work/'data', source_url=source['source_url'],
    content_sha256=source['raw_asset_id'][7:], accession=source['accession'], document_name=source['document_name'],
    request_attempt_id=source['request_attempt_id'], require_immutable=True)
assert proof['request_repo_relative_path'] == blobs[source['raw_asset_id']]['storage_uri']
target = work/'data'/proof['request_headers_repo_relative_path']
original_header = target.read_bytes()
install_worker_guards(runtime)
with historical_compute_scope():
    start = time.monotonic()
    positive = render_historical_run(data_root=work/'data', run_dir=work/'runs/C01', frozen=True)
    positive_seconds = time.monotonic()-start
    target.chmod(target.stat().st_mode | 0o200)
    target.write_bytes(original_header+b'\nBOUND_RUN_HEADER_NEGATIVE\n')
    start = time.monotonic()
    try:
        render_historical_run(data_root=work/'data', run_dir=work/'runs/C01', frozen=True)
    except Exception as error:
        reason = str(error)
        assert any(marker in reason for marker in ('COMPANY_SOURCE_BYTES_CHANGED',
            'HEADERS', 'HEADER', 'SOURCE_PROOF', 'CONTENT_HASH', 'METADATA')), reason
    else:
        raise AssertionError('changed Run-bound header accepted in warmed scope')
    negative_seconds = time.monotonic()-start
assert {path: sha256_file(path=Path(path)) for path in sealed} == sealed
report = {'status':'PASSED', 'uid':os.getuid(), 'runtime':str(runtime),
    'source_reference_id':source['source_reference_id'], 'request_attempt_id':source['request_attempt_id'],
    'bound_header':proof['request_headers_repo_relative_path'], 'positive_seconds':positive_seconds,
    'negative_seconds':negative_seconds, 'refusal':reason, 'old_success_files_unchanged':len(sealed),
    'same_process_scope_invalidated_changed_data':True, 'new_business_calls':[0,0,0]}
(output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))

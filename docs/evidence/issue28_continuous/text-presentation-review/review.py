import copy
import csv
import hashlib
import html
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

ROOT = Path('/Users/lyuhongwang/Developer/SEC_metrics')
BASE = Path('/tmp/sec_metrics_issue28_continuous/v13-open-acceptance-fb76')
OUT = Path(__file__).parent
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from vnext.normal_text_projection_v2 import _render_verified_text_records, render_normal_text_run
from vnext.normal_numeric_projection import project_normal_numeric_records
from vnext.specs import compile_spec_file
from vnext.run_store import RunStoreError

FILES = ['scripts/vnext/normal_text_projection_v2.py', 'config/normal_text_projection_v2.json', 'tools/vnext_normal_candidate.py']
before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FILES}
checks = []
rendered_cases = {}
native_cases = {}

def load(name):
    case = BASE / name
    manifest = json.loads((case / 'run/manifest.json').read_text())
    records = [json.loads(x) for x in (case / 'run/records.jsonl').read_text().splitlines()]
    binding = json.loads((case / 'data/normal_current_bindings' / (manifest['run_id'].split(':')[-1] + '.json')).read_text())
    return case, manifest, records, binding

for name, expected in [('marriott_international-C02', ('DEF 14A', '2026-03-27', 'PROXY', 29)),
                       ('paramount_skydance_paramount_global-C02', ('10-K/A', '2026-04-24', 'TEXT', 12)),
                       ('jpmorgan_chase-D02', ('10-K', '2026-02-13', 'MDA', 34))]:
    case, manifest, records, binding = load(name)
    # Private pure rendering only: old retained OPEN records are not replayed
    # under the current drifting V13 authority.
    rendered = _render_verified_text_records(data_root=case / 'data', manifest=manifest, records=records)
    result = next(x for x in records if x['record_type'] == 'METRIC_RESULT')
    observations = {x['observation_id']: x for x in records if x['record_type'] == 'VERIFIED_OBSERVATION'}
    trace = next(x for x in records if x['record_type'] == 'EXECUTION_TRACE' and x['trace_id'] == result['trace_id'])
    row = rendered['row']
    assert (row['form'], row['filed_date'], row['source_class'], len(rendered['evidence'])) == expected
    assert rendered['receipt']['run_status'] == 'OPEN'
    assert row['value'] == result['value']
    assert list(csv.DictReader(io.StringIO(rendered['files']['metrics_matrix.csv'].decode()))) == [row]
    assert list(csv.DictReader(io.StringIO(rendered['files']['metric_evidence.csv'].decode()))) == rendered['evidence']
    assert len(row) == 20 and all(len(e) == 18 for e in rendered['evidence'])
    assert [e['evidence_quote'] for e in rendered['evidence']] == [x['text'] for x in result['text_payload']['items']]
    for oid, evidence in zip(trace['input_observation_ids'], rendered['evidence']):
        observation = observations[oid]
        locator = observation['source_binding']['text_binding']
        raw = (case / 'data' / evidence['repo_relative_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == evidence['content_sha256']
        span = raw[locator['raw_start_byte']:locator['raw_end_byte']]
        assert hashlib.sha256(span).hexdigest() == locator['raw_span_sha256']
        text = ' '.join(html.unescape(re.sub('<[^>]+>', '', span.decode('utf-8'))).split())
        assert text == ' '.join(evidence['evidence_quote'].split())
        assert f":bytes:{locator['raw_start_byte']}-{locator['raw_end_byte']}:sha256:{locator['raw_span_sha256']}" in evidence['context_or_dimension']
    try:
        render_normal_text_run(data_root=case / 'data', run_dir=case / 'run')
    except RunStoreError as error:
        assert 'requires a FROZEN Run' in str(error), str(error)
    else:
        raise AssertionError('OPEN reached frozen projection')
    checks.append({'case': name, 'kind': 'PURE_RENDERING_ONLY', 'form': row['form'], 'filed_date': row['filed_date'],
                   'annual_grouping_period': rendered['receipt']['annual_grouping_period'],
                   'raw_byte_evidence_count': len(rendered['evidence']), 'open_frozen_entry': 'REJECTED'})
    (OUT / (name + '.json')).write_text(json.dumps({'review_credit':'PURE_RENDERING_ONLY_NOT_CURRENT_SOURCE_REPLAY',
        **{k:v for k,v in rendered.items() if k != 'files'}}, ensure_ascii=False, indent=2))
    rendered_cases[name] = rendered
    native_cases[name] = {'manifest': manifest, 'result': result, 'selection': None}

name = 'salesforce-C04'
case, manifest, records, binding = load(name)
result = next(x for x in records if x['record_type'] == 'METRIC_RESULT')
assert result['publication'] == 'WITHHELD'
assert not any(x['record_type'] == 'VERIFIED_OBSERVATION' for x in records)
selection = {'reason_code': result['reason_code'], 'details': binding['input_binding']['limitations']}
rendered = project_normal_numeric_records(repo_root=case / 'data', manifest=manifest, records=records,
    compiled_spec=compile_spec_file(path=case / 'data' / binding['spec_path'], dependency_specs={}),
    input_binding=binding, selection=selection)
assert rendered['row']['status'] == 'WITHHELD' and rendered['row']['value'] == ''
assert result['reason_code'] in rendered['row']['notes']
assert rendered['evidence'] == []
checks.append({'case':name, 'kind':'PURE_RENDERING_ONLY', 'status':'WITHHELD', 'reason':result['reason_code'],
               'source_count':len(rendered['receipt']['source_scope'])})
rendered_cases[name] = rendered
native_cases[name] = {'manifest': manifest, 'result': result, 'selection': selection}

spec = importlib.util.spec_from_file_location('review_cli', ROOT / 'tools/vnext_normal_candidate.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
for name in ('marriott_international-C02', 'salesforce-C04'):
    company, metric = name.rsplit('-', 1)
    directory = OUT / ('TEST_ONLY_mocked_cli_' + name)
    # Test CLI dispatch/serialization only. Both source acquisition and Run
    # producer are mocks; no actual installed or frozen candidate is created.
    payload = copy.deepcopy(native_cases[name])
    payload['manifest']['status'] = 'FROZEN'
    payload['manifest']['run_id'] = 'TEST_ONLY_MOCKED_CLI_NO_RUN_CREATED'
    renderer_name = 'render_normal_text_run' if metric == 'C02' else 'render_normal_numeric_run'
    with patch.object(cli, 'install_normal_inputs') as install, patch.object(cli, 'create_normal_run', return_value=payload) as create, \
         patch.object(cli, renderer_name, return_value=rendered_cases[name]) as renderer:
        status = cli.main(['--output-root', str(directory), '--company', company, '--metric', metric])
        assert create.call_args.kwargs['freeze'] is True
        assert renderer.call_count == 1
    summary = json.loads((directory / 'summary.json').read_text())
    coordinate = summary['coordinates'][0]
    assert coordinate['public_row_status'] == 'CANDIDATE_ROW_PREPARED'
    assert coordinate['status'] != 'INPUT_OR_EXECUTION_FAILED'
    assert (directory / 'rows' / company / metric / 'metrics_matrix.csv').exists()
    assert status == (0 if metric == 'C02' else 2)
    checks.append({'case':name, 'kind':'TEST_ONLY_MOCKED_CLI_DISPATCH_NO_RUN', 'exit_code':status,
                   'selection_none_allowed':metric == 'C02', 'row_written':True})

after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FILES}
assert before == after
report = {'record_type':'INDEPENDENT_TEXT_PROJECTION_READONLY_REVIEW', 'files':before, 'checks':checks,
          'repo_files_changed':False, 'installed_or_frozen_runs_created':False,
          'current_v13_source_replay_credit':False, 'calls':[0,0,0]}
(OUT / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(report, ensure_ascii=False, indent=2))

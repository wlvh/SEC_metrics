"""Read saved company results and sources without replaying or copying attempts.

This is a daily view, not an independent content review or a portable audit
archive. It checks stored records, coordinates, rows and referenced source
bytes, and keeps current source status and known defects visible.
"""
import csv
import io
import json
import os
from pathlib import Path
from uuid import uuid4

from .canonical import (arithmetic_context, canonical_json_bytes,
                        parse_decimal, sha256_file, strict_json_file, strict_json_loads)
from .company_handoff import external, locked_company
from .company_result_view import build_company_view, recover_for_read
from .company_source_authority import need
from .normal_source_authority import ROOT
from .csv_output import METRIC_FIELDS, EVIDENCE_FIELDS, _csv_bytes
from .records import validate_record
from .sources import resolve_repository_file
from .specs import compile_spec_files

DAILY_FIELDS = ('company_id', 'run_id', 'result_id', 'requirement_id', 'requirement_closure_hash',
    'source_checkpoint_id', 'current_source_checkpoint_id', 'current_input_matches',
    'current_input_status', 'latest_attempt_status', 'latest_request_status', 'result_validity',
    'source_credit', 'source_import_status', 'source_freshness', 'record_root', 'source_root',
    'archive_period_start', 'archive_period_end', 'archive_fiscal_year',
    'measurement_period_start', 'measurement_period_end', 'measurement_period_status', 'defect_holds',
    'requested_in_latest_execution', 'period_role')


def _rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))


def read_saved_candidate(entry, checked_sources=None):
    """Check a saved result, not its calculation or model's semantic judgment."""
    metric = entry['metric_id']; work = Path(entry['rows_root']).parent
    run = work/'runs'/metric; data = work/'data'
    manifest = strict_json_file(path=run/'manifest.json')
    need(manifest['company_id'] == entry['company_id'] and manifest['run_id'] == entry['run_id'],
         'DAILY_RESULT_RUN_COORDINATE_CHANGED')
    records = [strict_json_loads(text=l) for l in (run/'records.jsonl').read_text().splitlines()]
    matches = [r for r in records if r.get('record_type') == 'METRIC_RESULT'
               and r.get('metric_id') == metric and r.get('result_id') == entry['result_id']]
    need(len(matches) == 1, 'DAILY_RESULT_RECORD_MISSING_OR_DUPLICATE')
    result = validate_record(record=matches[0])
    need(result['company_id'] == entry['company_id'], 'DAILY_RESULT_WRONG_COMPANY')
    traces = [r for r in records if r.get('record_type') == 'EXECUTION_TRACE'
              and r.get('trace_id') == result['trace_id']]
    need(len(traces) == 1, 'DAILY_RESULT_TRACE_MISSING')
    trace = validate_record(record=traces[0])
    need(trace['metric_id'] == metric and trace['spec_closure_hash'] == result['spec_closure_hash']
         and all(trace['calculation_target'][k] == result[k]
                 for k in ('company_id','period_start','period_end','scope_key')), 'DAILY_RESULT_TRACE_COORDINATE_CHANGED')
    specs = []
    for relative, expected in manifest['spec_file_hashes'].items():
        path = resolve_repository_file(repo_root=data, repo_relative_path=relative)
        need(sha256_file(path=path) == expected, 'DAILY_RESULT_SPEC_FILE_CHANGED')
        specs.append(path)
    spec = compile_spec_files(paths=specs)[metric]
    need(spec['spec_closure_hash'] == result['spec_closure_hash'], 'DAILY_RESULT_SPEC_CHANGED')
    need(result['unit'] == spec['compiled']['canonical_unit'] or
         result['unit'] is None and result['value'] is None, 'DAILY_RESULT_UNIT_CHANGED')
    directory = Path(entry['rows_root']) if entry['row_layout'] == 'historical' else Path(entry['rows_root'])/metric
    files = {n: (directory/n).read_bytes() for n in ('metrics_matrix.csv', 'metric_evidence.csv')}
    # Old ordinary journals already retain row hashes. Other saved formats
    # still undergo record/value/source checks; they do not gain replay credit.
    if (work/'terminal.json').is_file():
        terminal = strict_json_file(path=work/'terminal.json')
        expected = terminal.get('metrics', {}).get(metric, {}).get('files', {})
        for name, digest in expected.items():
            need(name in files and sha256_file(path=directory/name) == digest, 'DAILY_RESULT_ROWS_CHANGED')
    projected = _rows(files['metrics_matrix.csv']); need(len(projected) == 1, 'DAILY_RESULT_ROW_SET_CHANGED')
    row = projected[0]
    need(row['metric_id'] == metric and all(row[k] == result[k] for k in ('period_start','period_end')),
         'DAILY_RESULT_MEASUREMENT_CHANGED')
    need(row['fiscal_year'] == str(manifest['target_period']['fiscal_year']), 'DAILY_RESULT_FISCAL_LABEL_CHANGED')
    projection = spec['compiled']['legacy_projection']
    need(row['unit'] == projection.get('unit', spec['compiled']['canonical_unit']), 'DAILY_RESULT_ROW_UNIT_CHANGED')
    if result.get('value_kind') != 'TEXT_V1' and result['value'] is not None:
        with arithmetic_context():
            expected = parse_decimal(value=result['value']) * parse_decimal(value=projection.get('value_multiplier','1'))
            need(parse_decimal(value=row['value']) == expected, 'DAILY_RESULT_VALUE_CHANGED')
    elif result.get('value_kind') == 'TEXT_V1' and result['value'] is not None:
        need(row['value'] == result['value'], 'DAILY_RESULT_TEXT_VALUE_CHANGED')
    elif result.get('value_kind') != 'TEXT_V1':
        need(row['value'] == '', 'DAILY_RESULT_ABSENT_VALUE_CHANGED')
    evidence = _rows(files['metric_evidence.csv'])
    raw = {r['raw_asset_id']: r for r in records if r.get('record_type') == 'RAW_BLOB'}
    refs = [r for r in records if r.get('record_type') == 'SOURCE_REFERENCE']
    checked_sources = {} if checked_sources is None else checked_sources
    for item in evidence:
        need(item['metric_id'] == metric, 'DAILY_RESULT_EVIDENCE_WRONG_METRIC')
        candidates = [r for r in refs if r['source_url'] == item['source_url']
                      and r['accession'] == item['accession'] and r['document_name'] == item['document_name']]
        need(candidates and any(r['raw_asset_id'] == 'sha256:'+item['content_sha256']
             and r['company_id'] == entry['company_id'] for r in candidates), 'DAILY_RESULT_SOURCE_REFERENCE_MISSING')
        blob = raw.get('sha256:'+item['content_sha256'])
        need(blob is not None and blob['storage_uri'] == item['repo_relative_path'], 'DAILY_RESULT_SOURCE_PATH_CHANGED')
        path = resolve_repository_file(repo_root=data, repo_relative_path=blob['storage_uri'])
        key = (str(path), path.stat().st_size, path.stat().st_mtime_ns)
        if key not in checked_sources:
            checked_sources[key] = sha256_file(path=path)
        need(checked_sources[key] == item['content_sha256'], 'DAILY_RESULT_SOURCE_BYTES_CHANGED')
    return {'row': row, 'evidence': evidence, 'result': result,
            'record_root': str(run), 'source_root': str(data)}


def write_daily_results(*, state_root, output_root, company_id, runtime_roots=(), defects_file=None):
    """Atomically write daily CSV/JSON; explicit audit export remains separate."""
    output = external(output_root); need(not output.exists(), 'DAILY_RESULT_OUTPUT_EXISTS')
    with locked_company(state_root) as root:
        need(root != output and root not in output.parents and output not in root.parents,
             'DAILY_RESULT_STATE_OVERLAP')
        current = recover_for_read(root, runtime_roots)
        need(current and current['company_id'] == company_id, 'DAILY_RESULT_WRONG_COMPANY')
        registry_path = Path(defects_file) if defects_file else ROOT/'docs/evidence/issue28_continuous/known_result_defects.json'
        registry = strict_json_file(path=registry_path) if registry_path.is_file() else None
        need(defects_file is None or registry is not None, 'DAILY_RESULT_DEFECT_REGISTER_MISSING')
        view = build_company_view(root=root, company_id=company_id, current=current, defect_registry=registry)
        source_import = strict_json_file(path=root/'latest_import.json') if (root/'latest_import.json').is_file() else {}
        metric_rows, evidence_rows, checked_sources = [], [], {}
        for entry in view['metrics']:
            entry.update(source_import_status=source_import.get('status','NOT_AVAILABLE'),
                         source_freshness='SAVED_VERSION_ONLY_NOT_ONLINE_CHECKED')
            if not entry.get('run_id'):
                period = entry.get('period_request') or {}
                latest = view.get('latest_execution') or {}
                entry.update(period_role='REQUESTED_WITHOUT_RESULT',
                    requested_in_latest_execution=entry['metric_id'] in latest.get('metric_ids',
                        [m['metric_id'] for m in latest.get('metrics',[])])
                        and period == (latest.get('period_request') or {}))
                metric_rows.append({'metric_id': entry['metric_id'], 'status':entry['latest_attempt_status'],
                    'fiscal_year':period.get('fiscal_year',''), 'period_end':period.get('report_end',''),
                    'notes':entry.get('reason'), **{k:entry.get(k) for k in DAILY_FIELDS}})
                continue
            # A different code-package identity alone is no longer a content
            # defect. Retain the prior same-result release reference without
            # manufacturing a new content acceptance. Actual unreleased
            # defects remain held by result/metric/period, as before.
            entry['prior_same_result_releases'] = [h for h in entry.get('defect_holds',[])
                if h['reason'] == 'CURRENT_RUNTIME_RELEASE_REQUIRED']
            entry['defect_holds'] = [h for h in entry.get('defect_holds',[])
                if h['reason'] != 'CURRENT_RUNTIME_RELEASE_REQUIRED']
            entry['confirmed_defects'] = [h['defect_id'] for h in entry['defect_holds']]
            held = bool(entry['defect_holds'])
            try:
                saved = read_saved_candidate(entry, checked_sources)
                entry.update(record_root=saved['record_root'], source_root=saved['source_root'],
                    measurement_period={k:saved['result'][k] for k in ('period_start','period_end')},
                    measurement_period_status='SAVED_RECORD_CHECKED_NOT_REPLAYED', replay_status='NOT_REPLAYED')
                if not held: entry['result_validity'] = 'SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED'
                entry.update(archive_period_start=entry['period'].get('period_start'),
                    archive_period_end=entry['period'].get('period_end'), archive_fiscal_year=entry['period'].get('fiscal_year'),
                    measurement_period_start=saved['result']['period_start'], measurement_period_end=saved['result']['period_end'])
                metadata = {k:entry.get(k) for k in DAILY_FIELDS}
                metadata['defect_holds'] = json.dumps(entry.get('defect_holds',[]),ensure_ascii=False)
                row = saved['row']
                if held:
                    row = {**row, 'value':'', 'status':'WITHHELD',
                        'notes':row.get('notes','')+'; '+entry['result_validity']+':'+','.join(entry['confirmed_defects'])}
                elif entry.get('current_input_matches') is False or source_import.get('status') == 'FAILED':
                    row = {**row, 'status':'PREVIOUS_RESULT',
                        'notes':row.get('notes','')+'; Latest source/update failed or differs; this is the saved previous result.'}
                metric_rows.append({**row, **metadata})
                evidence_rows.extend({**e, **metadata} for e in saved['evidence'])
            except Exception as error:
                entry.update(saved_read_status='FAILED', reason=str(error))
                if not held: entry['result_validity'] = 'SAVED_RECORD_INVALID'
                metric_rows.append({'metric_id':entry['metric_id'], **entry['period'],
                    **{k:entry.get(k) for k in DAILY_FIELDS}, 'status':'WITHHELD', 'notes':str(error)})
        output.parent.mkdir(parents=True,exist_ok=True)
        staged = output.with_name('.'+output.name+'-'+uuid4().hex); staged.mkdir()
        try:
            for name, rows, fields in [('metrics_matrix.csv',metric_rows,(*METRIC_FIELDS,*DAILY_FIELDS)),
                                      ('metric_evidence.csv',evidence_rows,(*EVIDENCE_FIELDS,*DAILY_FIELDS))]:
                (staged/name).write_bytes(_csv_bytes(rows=[{k:r.get(k,'') for k in fields} for r in rows],fieldnames=fields))
            (staged/'company-results.json').write_bytes(canonical_json_bytes(value=view))
            report = {'record_type':'COMPANY_DAILY_RESULT_VIEW_V1','company_id':company_id,
                'output_root':str(output),'status':'READ_PARTIAL' if any(e.get('saved_read_status')=='FAILED' for e in view['metrics']) else 'READ',
                'result_count':len(view['metrics']),'replay_performed':False,'attempts_copied':False,
                'new_business_calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
            (staged/'read.json').write_bytes(canonical_json_bytes(value=report)); os.rename(staged,output)
            return report
        except Exception:
            import shutil
            shutil.rmtree(staged); raise

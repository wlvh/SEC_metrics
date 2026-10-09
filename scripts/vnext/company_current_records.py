"""Saved-source company runs sharing program/source roots and small records.

This is the current deterministic branch of the existing company CLI. It does
not acquire sources or call a model. Native histories retain their old reader.
"""
import csv
import fcntl
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .canonical import strict_json_file
from .company_handoff import _atomic_json
from .csv_output import METRIC_FIELDS, EVIDENCE_FIELDS, _csv_bytes
from .normal_source_authority import ROOT
from .ordinary_current_update import run_once
from .ordinary_saved_result import SAVED_METRIC_IDS, read_saved_result

EXTRA_FIELDS = ('company_id', 'result_id', 'record_root', 'source_root',
                'local_metric_status', 'period_role', 'result_validity',
                'source_observation_status', 'defect_holds', 'requested_in_latest_execution')
# Old E01 item-code counts do not satisfy the adopted content-confirmed M&A
# definition. Keep them in old records, not the new company's current result.
CURRENT_METRICS = SAVED_METRIC_IDS - {'E01'}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))


def _registry(defects_file=None):
    saved = strict_json_file(path=ROOT/'docs/evidence/issue28_continuous/known_result_defects.json')
    if defects_file is not None:
        other = strict_json_file(path=Path(defects_file))
        saved = {**saved, 'defects': [*saved.get('defects', []), *other.get('defects', [])]}
    return saved


def _defects(result, registry):
    """Hold exact known results; code packaging cannot erase their defects."""
    return [d['defect_id'] for d in registry.get('defects', [])
            if (d.get('company_id'), d.get('metric_id'), d.get('period_end')) ==
               (result['company_id'], result['metric_id'], result['period_end'])
            and (not d.get('result_id') or d['result_id'] == result['result_id'])
            and not any(r.get('result_id') == result['result_id'] for r in
                        ([d['released']] if isinstance(d.get('released'), dict)
                         else d.get('released', [])))]


def run_saved_company(*, company_id, source_root, work_dir, output_dir,
                      metric_ids=None, defects_file=None, fiscal_years=None, case_factory=None,
                      processing_files=()):
    """Calculate changed inputs and read durable results into ordinary CSVs."""
    from .normal_annual_input import _registry_rows
    from .deterministic_router import shared_xbrl_parses
    source, work, outputs = (Path(p).resolve() for p in (source_root, work_dir, output_dir))
    _need(source.is_dir(), 'COMPANY_SAVED_SOURCE_ROOT_MISSING')
    roots = (source, work, outputs, ROOT.resolve())
    for i, left in enumerate(roots[:3]):
        for right in roots[i+1:]:
            # Reading sources already in a checkout is valid; writes must
            # remain outside program/source roots and each other.
            if i == 0 and right == ROOT.resolve():
                continue
            _need(left != right and left not in right.parents and right not in left.parents,
                  'COMPANY_CURRENT_ROOTS_OVERLAP')
    companies = {r['company_id']: r for r in _registry_rows(repo_root=ROOT)}
    _need(company_id in companies, 'COMPANY_CURRENT_UNKNOWN_COMPANY')
    configured = strict_json_file(path=ROOT/'config/source_strategy_registry.json')['metrics']
    selected = sorted(configured) if metric_ids is None else list(metric_ids)
    _need(selected and len(selected) == len(set(selected)) and set(selected) <= set(configured),
          'COMPANY_CURRENT_METRIC_SCOPE_INVALID')
    _need(fiscal_years is None or type(fiscal_years) in (list,tuple) and 0<len(fiscal_years)<=5
          and all(type(y) is int and 1900<=y<=9998 for y in fiscal_years)
          and len(fiscal_years)==len(set(fiscal_years)), 'COMPANY_CURRENT_FISCAL_YEAR_SCOPE_INVALID')
    _need((fiscal_years is None and case_factory is None) or fiscal_years is not None and callable(case_factory),
          'COMPANY_CURRENT_SELECTED_YEARS_REQUIRE_CASE_FACTORY')
    registry = _registry(defects_file)
    work.mkdir(parents=True, exist_ok=True)
    _need(not (work/'local-company.json').exists() and not (work/'current_source.json').exists(),
          'COMPANY_CURRENT_OLD_TASK_REQUIRES_ORIGINAL_ENTRY')
    with (work/'company.lock').open('a+b') as lock, shared_xbrl_parses():
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = {'record_type': 'ORDINARY_COMPANY_TASK_V1', 'company_id': company_id,
                  'source_root': str(source)}
        config_path = work/'company-task.json'
        if config_path.is_file():
            _need(strict_json_file(path=config_path) == config, 'COMPANY_CURRENT_TASK_IDENTITY_CHANGED')
        else:
            _atomic_json(config_path, config)
        key = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]
        output = outputs/key
        output.mkdir(parents=True)
        observations, matrix, evidence = [], [], []
        scopes = [(year,metric) for year in ([None] if fiscal_years is None else fiscal_years) for metric in selected]
        for year,metric in scopes:
            controller = work/'updates'/metric
            period_controller = controller if year is None else controller/'periods'/('FY'+str(year))
            if metric not in CURRENT_METRICS:
                observation = {'metric_id': metric, 'status': 'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED',
                               'reason': 'This saved-source branch has no complete current processing interface for '+metric}
            else:
                try:
                    observation = {'metric_id': metric, **run_once(state_root=controller,
                        source_root=source, company_id=company_id, metric_id=metric,
                        shared_input_root=work/'shared-inputs',fiscal_year=year,case_factory=case_factory,
                        processing_files=processing_files)}
                except Exception as error:
                    observation = {'metric_id': metric, 'status': 'INPUT_OR_EXECUTION_FAILED',
                                   'reason': str(error), 'error_type': type(error).__name__}
            observations.append(observation)
            if year is not None:observation['requested_fiscal_year']=year
            pointer = period_controller/'current-result.json'
            previous = observation['status'] not in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'}
            new_record = (observation.get('result_root')
                          if observation['status'] in {'CANDIDATE_WITHHELD','PREVIOUS_INPUT_WITHHELD'} else None)
            if pointer.is_file() or new_record:
                try:
                    state = strict_json_file(path=pointer) if pointer.is_file() else None
                    record = Path(new_record) if new_record else period_controller/'results'/state['version']
                    saved = read_saved_result(output_root=record)
                    result = saved['result']
                    _need(result['company_id'] == company_id and result['metric_id'] == metric,
                          'COMPANY_CURRENT_WRONG_SAVED_COORDINATE')
                    holds = _defects(result, registry)
                    observation['defect_holds'] = holds
                    row = _rows(saved['files']['metrics_matrix.csv'])[0]
                    if holds:
                        row.update(value='', unit='', status='WITHHELD_KNOWN_DEFECT',
                                   notes=row.get('notes', '')+'; '+','.join(holds))
                    row.update(company_id=company_id, result_id=result['result_id'],
                        record_root=str(record), source_root=str(source),
                        local_metric_status=observation['status'], period_role='PREVIOUS_RESULT' if previous and not new_record else 'REQUESTED_RESULT',
                        result_validity='CONFIRMED_INVALID' if holds else 'SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED',
                        source_observation_status=('FAILED_CURRENT_CHECK' if previous and not new_record else
                            'SAVED_SOURCE_CHECKED_WITH_DISCOVERY_ERRORS' if observation.get('source_observation_errors') else
                            'SAVED_SOURCE_CHECKED_NOT_ONLINE_REFRESHED'),
                        defect_holds=json.dumps(holds))
                    row['requested_in_latest_execution'] = True
                    matrix.append(row)
                    evidence.extend(_rows(saved['files']['metric_evidence.csv']))
                    observation['read_result_id'] = result['result_id']
                    observation['record_root'] = str(record)
                    observation['program_version'] = saved.get('manifest', {}).get('program_version')
                    continue
                except Exception as error:
                    observation['saved_read_error'] = str(error)
            matrix.append({**{f: '' for f in (*METRIC_FIELDS, *EXTRA_FIELDS)},
                'company': companies[company_id]['display_name'], 'company_id': company_id,
                'metric_id': metric, 'status': observation['status'], 'notes': observation.get('reason', ''),
                'local_metric_status': observation['status'], 'result_validity': 'NO_CURRENT_RESULT',
                'period_role': 'REQUESTED_WITHOUT_RESULT', 'source_root': str(source),
                'requested_in_latest_execution': True})
            if year is not None:matrix[-1]['fiscal_year']=str(year)
        complete = all(o['status'] in {'CANDIDATE_READY', 'NO_SOURCE_CONTENT_CHANGE'}
                       and not o.get('defect_holds') and not o.get('saved_read_error')
                       and not o.get('source_observation_errors') for o in observations)
        report = {'record_type': 'ORDINARY_COMPANY_EXECUTION_V1', 'company_id': company_id,
            'run_id': key, 'status': 'FLOW_COMPLETED' if complete else 'FLOW_COMPLETED_WITH_LIMITATIONS',
            'selected_metrics': selected, 'metrics': observations, 'source_root': str(source),
            'program_root': str(ROOT), 'record_root': str(work), 'output_root': str(output),
            'source_mode': 'SAVED_ONLY_NO_ONLINE_DISCOVERY',
            'calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'production_authorized': False}
        if fiscal_years is not None:report['selected_fiscal_years']=list(fiscal_years)
        # No copytree, native replay, trust installation or rule sealing.
        for name, raw in (('metrics_matrix.csv', _csv_bytes(rows=matrix, fieldnames=(*METRIC_FIELDS, *EXTRA_FIELDS))),
                          ('metric_evidence.csv', _csv_bytes(rows=evidence, fieldnames=EVIDENCE_FIELDS))):
            temporary = output/('.'+name)
            temporary.write_bytes(raw)
            temporary.replace(output/name)
        _atomic_json(output/'company-results.json', report)
        _atomic_json(output/'run_summary.json', report)
        _atomic_json(work/'latest-execution.json', report)
        return report


def read_current_company(*, state_root, company_id, defects_file=None, output_root=None):
    """Read ordinary records without parsing sources or running an update."""
    root = Path(state_root).resolve()
    with (root/'company.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        return _read_current_company(root, company_id, defects_file, output_root)


def _read_current_company(root, company_id, defects_file, output_root):
    task = strict_json_file(path=root/'company-task.json')
    _need(task['record_type'] == 'ORDINARY_COMPANY_TASK_V1' and task['company_id'] == company_id,
          'COMPANY_CURRENT_WRONG_TASK')
    registry = _registry(defects_file)
    report = strict_json_file(path=root/'latest-execution.json')
    _need(report['company_id'] == company_id, 'COMPANY_CURRENT_WRONG_EXECUTION')
    def normalize(observation):
        value = dict(observation)
        value.setdefault('record_root',value.get('result_root'))
        value.setdefault('read_result_id',value.get('result_id'))
        return value

    def coordinate(observation):
        year = observation.get('requested_fiscal_year')
        path = observation.get('record_root')
        if path and (Path(path)/'manifest.json').is_file():
            year = strict_json_file(path=Path(path)/'manifest.json')['target_period']['fiscal_year']
        return observation['metric_id'],year

    observations = {coordinate(normalize(m)): {**normalize(m), 'requested_in_latest_execution': True}
                    for m in report['metrics']}
    controllers={p.parent for name in ('current-result.json','completed-check.json')
                 for p in (root/'updates').glob('**/'+name)}
    for controller in sorted(controllers):
        completed=controller/'completed-check.json'
        pointer=completed if completed.is_file() else controller/'current-result.json'
        state = strict_json_file(path=pointer)
        metric = state['metric_id']
        _need(state['company_id'] == company_id, 'COMPANY_CURRENT_READ_POINTER_COORDINATE_CHANGED')
        if pointer==completed:
            _need(state['status'] in {'CANDIDATE_READY','CANDIDATE_WITHHELD'},
                  'COMPANY_CURRENT_READ_COMPLETED_STATUS_INVALID')
        stored = {'metric_id': metric, 'status': 'NOT_REQUESTED_IN_LATEST_EXECUTION',
            'record_root': str(pointer.parent/'results'/state['version']), 'read_result_id': state['result_id'],
            'requested_fiscal_year':state.get('requested_fiscal_year'), 'requested_in_latest_execution': False}
        if pointer==completed:stored['completed_conclusion']=state['status']
        key = coordinate(stored)
        if key not in observations:observations[key] = stored
    rows, matrix, evidence = [], [], []
    shared_record_cache = {}
    for observation in observations.values():
        record = observation.get('record_root')
        if record:
            record = Path(record).resolve()
            _need(root in record.parents, 'COMPANY_CURRENT_RECORD_OUTSIDE_STATE')
            saved = read_saved_result(output_root=record, shared_record_cache=shared_record_cache)
            result = saved['result']
            _need(result['company_id'] == company_id and result['metric_id'] == observation['metric_id']
                  and result['result_id'] == observation['read_result_id'], 'COMPANY_CURRENT_READ_COORDINATE_CHANGED')
            conclusion=observation.get('completed_conclusion')
            if conclusion is not None:
                _need(result.get('publication')==('PUBLISHED' if conclusion=='CANDIDATE_READY' else 'WITHHELD'),
                      'COMPANY_CURRENT_READ_COMPLETED_PUBLICATION_CHANGED')
            holds = _defects(result, registry)
            scope_ready = result['metric_id'] in CURRENT_METRICS
            rows.append({'metric_id': result['metric_id'], 'result_id': result['result_id'],
                'period_start': result.get('period_start'), 'period_end': result['period_end'],
                'fiscal_year':saved['manifest']['target_period']['fiscal_year'],
                'value': None if holds or not scope_ready else result.get('value'),
                'unit': None if holds or not scope_ready else result.get('unit'),
                'publication':result.get('publication'),'quality':result.get('quality'),
                'reason_code':result.get('reason_code'),
                'result_validity': ('CONFIRMED_INVALID' if holds else 'CURRENT_SCOPE_NOT_READY' if not scope_ready
                                    else 'SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED'),
                'defect_holds': holds, 'latest_observation': observation['status'],
                'requested_in_latest_execution': observation['requested_in_latest_execution'],
                'record_root': str(record)})
            csv_row = _rows(saved['files']['metrics_matrix.csv'])[0]
            if holds:
                csv_row.update(value='', unit='', status='WITHHELD_KNOWN_DEFECT',
                    notes=csv_row.get('notes', '')+'; '+','.join(holds))
            elif not scope_ready:
                csv_row.update(value='',unit='',status='WITHHELD_CURRENT_SCOPE_NOT_IMPLEMENTED')
            csv_row.update(company_id=company_id, result_id=result['result_id'], record_root=str(record),
                source_root=task['source_root'], local_metric_status=observation['status'],
                period_role=('SAVED_RESULT_NOT_REQUESTED' if not observation['requested_in_latest_execution'] else
                             'PREVIOUS_RESULT' if observation['status']=='INPUT_OR_EXECUTION_FAILED' else 'REQUESTED_RESULT'),
                result_validity=rows[-1]['result_validity'], source_observation_status='NOT_CHECKED_BY_SAVED_READER',
                defect_holds=json.dumps(holds), requested_in_latest_execution=observation['requested_in_latest_execution'])
            matrix.append(csv_row)
            evidence.extend(_rows(saved['files']['metric_evidence.csv']))
        else:
            rows.append({'metric_id': observation['metric_id'], 'value': None,
                         'result_validity': 'NO_CURRENT_RESULT', 'latest_observation': observation['status'],
                         'fiscal_year':observation.get('requested_fiscal_year'),
                         'requested_in_latest_execution': observation['requested_in_latest_execution']})
            matrix.append({**{f:'' for f in (*METRIC_FIELDS,*EXTRA_FIELDS)},
                'company_id':company_id,'metric_id':observation['metric_id'],'status':observation['status'],
                'local_metric_status':observation['status'],'result_validity':'NO_CURRENT_RESULT',
                'period_role':'REQUESTED_WITHOUT_RESULT','source_root':task['source_root'],
                'source_observation_status':'NOT_CHECKED_BY_SAVED_READER',
                'requested_in_latest_execution':observation['requested_in_latest_execution']})
            if observation.get('requested_fiscal_year') is not None:
                matrix[-1]['fiscal_year']=str(observation['requested_fiscal_year'])
    view = {'record_type': 'ORDINARY_COMPANY_RESULT_VIEW_V1', 'company_id': company_id,
        'source_root': task['source_root'], 'metrics': rows, 'source_freshness': 'NOT_CHECKED_BY_SAVED_READER',
        'calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'production_authorized': False}
    if output_root is not None:
        output = Path(output_root).resolve()
        for protected in (root,Path(task['source_root']).resolve(),ROOT.resolve()):
            _need(output != protected and output not in protected.parents and protected not in output.parents,
                  'COMPANY_CURRENT_EXPORT_ROOT_OVERLAP')
        _need(not output.exists(), 'COMPANY_CURRENT_EXPORT_OUTPUT_EXISTS')
        output.mkdir(parents=True)
        from sec_http import write_immutable_bytes
        write_immutable_bytes(path=output/'metrics_matrix.csv',
            content=_csv_bytes(rows=matrix,fieldnames=(*METRIC_FIELDS,*EXTRA_FIELDS)))
        write_immutable_bytes(path=output/'metric_evidence.csv',
            content=_csv_bytes(rows=evidence,fieldnames=EVIDENCE_FIELDS))
        _atomic_json(output/'company-results.json',view)
        view['output_root'] = str(output)
    return view

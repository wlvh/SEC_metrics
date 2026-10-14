"""Saved-source updates: compare first, calculate changed input, retain versions.

This current zero-egress path uses ordinary records. Old native journals keep
their explicit old controller; no historic record or quota is migrated here.
"""
import fcntl
import json
from pathlib import Path
from uuid import uuid4
import re
import inspect
from urllib.parse import urlsplit

from .annual_sources import _rows
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .ordinary_saved_result import (METRIC_IDS, SAVED_METRIC_IDS, EXPLICIT_CASE_METRICS,
    CURRENT_FINANCIAL_METRICS, CURRENT_E01_SPEC_PATH, current_e01_scope,
    create_saved_result, read_saved_result, save_calculated_case)
from .traits import repository_company_ciks


def _need(condition, reason):
    if not condition: raise ValueError(reason)


def _write(path, value):
    from .company_handoff import _atomic_json
    path.parent.mkdir(parents=True,exist_ok=True); _atomic_json(path,value)


def _configuration(source, company, metric, *, supplied_case=False):
    policy = strict_json_file(path=ROOT/'config/issue28_normal_results_v2.json')
    paths = set(policy['rule_paths']) | set(policy['presentation_paths'])
    # Ordinary records verify saved inputs directly, without registering a
    # legacy RecordedSourceSession. Consumers that actually use that session
    # may still name it explicitly in run_once(processing_files=...).
    paths.discard('scripts/vnext/ordinary_source_session.py')
    if metric == 'E01':
        # Both event-item and content-confirmed E01 prepare annual/event
        # sources; neither executes D02's legal-excerpt/page selection.
        # Explicit D02 consumers still retain this processing dependency.
        paths.discard('scripts/vnext/d02_text_results_v3.py')
    # These files belong solely to the lodging producer. The zero-AI Spec
    # set never prepares a lodging case; unrelated edits must not recalculate
    # B01/B02 or their other supported deterministic neighbours.
    if metric in METRIC_IDS or metric in CURRENT_FINANCIAL_METRICS:
        if metric in METRIC_IDS:
            paths.add('scripts/vnext/zero_ai_r2.py')
        paths.difference_update({'scripts/vnext/normal_lodging_results.py',
            'scripts/vnext/lodging_table_source.py', 'config/ordinary_lodging_table_v1.json',
            'catalog/ordinary_lodging/B10.md', 'catalog/ordinary_lodging/B11.md'})
    if metric in METRIC_IDS or metric == 'D04':
        # Neither zero-AI nor the saved D04 response producer calls B06 grammar.
        # Shared annual selection, source checks and financial calculation
        # remain below; an explicit historical consumer may add its own paths.
        paths.difference_update({
            'scripts/vnext/b06_bond_leases.py','scripts/vnext/b06_current_input.py',
            'scripts/vnext/b06_financing_inventory.py','scripts/vnext/b06_inclusive_table.py',
            'scripts/vnext/b06_note_carrying.py','scripts/vnext/normal_bond_debt_results.py',
            'scripts/vnext/normal_inclusive_debt_results.py','scripts/vnext/normal_note_debt_results.py',
            'scripts/vnext/ordinary_debt_guard.py','scripts/vnext/ordinary_special_debt_scope.py',
            'config/b06_bond_debt_set_v1.json','config/b06_bond_leases_v1.json',
            'config/b06_current_input_v1.json','config/b06_financing_inventory_v1.json',
            'config/b06_inclusive_table_v1.json','config/b06_note_carrying_v1.json',
            'config/b06_special_scope_v1.json','catalog/r5/B06_bond_leases_v5.md',
            'catalog/r5/B06_inclusive_table_v6.md','catalog/r5/B06_note_carrying_v4.md'})
    paths.update({'scripts/vnext/ordinary_current_update.py','scripts/vnext/ordinary_saved_result.py',
                  'scripts/vnext/csv_output.py','scripts/vnext/ordinary_update_compatibility.py','scripts/vnext/ordinary_result_registration.py',
                  'config/issue28_normal_results_v2.json'})
    # The old Requirement inherited these dependencies implicitly. Ordinary
    # records must name their actual shared parser/calculator dependencies.
    paths.update('scripts/vnext/'+name+'.py' for name in (
        'deterministic_router','calculator','canonical','records','observations',
        'specs','scope_contract','text_coverage','text_results_v2',
        'sources','table_grid','resource_limits','traits','projector',
        'governance_signals','annual_input','annual_sources','deterministic_catalog',
        'saved_source_checks','request_bindings','company_registry',
        'normal_annual_input'))
    # These URL constructors actually select saved source inputs. They are
    # outside vnext but share the same ordinary processing responsibility.
    paths.add('scripts/sec_urls.py')
    # Saved readers also execute its artifact/snapshot selection helpers,
    # beyond the manifest check repeated by the controller.
    paths.add('scripts/sec_http.py')
    # Source blocks, registered original reads and context interpretation are
    # business inputs of these actual annual factories, not check-only code.
    if metric in METRIC_IDS or metric in {'B06','C04','A13','D01'}:
        paths.update('scripts/vnext/'+name+'.py' for name in (
            'text_coverage','normal_governance_input','text_results_v2'))
    # Current producers import only ROOT from normal_source_authority; its
    # historical admission gates do not process this ordinary input. Actual
    # request/body checks are covered by saved_source_checks above.
    paths.update({'catalog/company_traits.yaml','config/metric_applicability.yaml',
                  'config/company_registry.csv'})
    from .normal_zero_ai_results import SUPPORTED_METRICS
    if metric in METRIC_IDS-set(SUPPORTED_METRICS)-{'A01','A02','B12'}:
        # The CompanyFacts factory runs this comparison guard while preparing
        # its components, including B04; it is not specific to revenue.
        paths.add('scripts/vnext/paired_measure_v1.py')
    if metric == 'B06':
        from .current_b06_case import PROCESSING_FILES
        paths.update(PROCESSING_FILES)
    if metric == 'A13':
        from .current_geography_case import PROCESSING_FILES
        paths.update(PROCESSING_FILES)
    if metric in {'B04','B07'}:
        from .current_statement_metric_case import PROCESSING_FILES
        paths.update(PROCESSING_FILES)
    if metric == 'C04':
        from .current_auditor_case import PROCESSING_FILES
        paths.update(PROCESSING_FILES)
    if metric == 'C02':
        # Only C02's existing selector now imports this pure name helper.
        # Explicit proxy C03 producers declare their own source dependencies.
        paths.add('scripts/vnext/organization_name_core.py')
    if metric in {'B01','B02','B03'}:
        paths.update('scripts/vnext/'+name+'.py' for name in (
            'selected_income_calculation',
            'selected_revenue_scope_v1','selected_reported_revenue_v2','selected_fiscal_definition_scope_v1','selected_income_source_v1',
            'historical_fiscal_labels','financial_structured',
            'financial_duration','text_results_v2','xbrl_namespace_policy','composite_scope'))
    if metric in {'B01','B03'}:
        paths.update('scripts/vnext/'+name+'.py' for name in (
            'historical_dei','batch_workflow','constraints'))
    if metric == 'B03':
        paths.add('catalog/r6/text_results_v2_policy.json')
        paths.update('scripts/vnext/'+name+'.py' for name in (
            'ordinary_da_scope_v1','ordinary_b03_input_scope','xbrl_namespace_policy','b03_depreciation_scope',
            'b03_contract_amortization_scope','financial_structured','text_results_v2','reported_monetary_literal'))
    if metric in CURRENT_FINANCIAL_METRICS:
        paths.update('scripts/vnext/'+name+'.py' for name in (
            'financial_results','financial_relationships','financial_duration',
            'composite_scope','constraints','r4_task_contracts','table_task_contracts',
            'annual_update','normal_annual_input_v2','fiscal_year_labels',
            'ordinary_source_authority','text_results_v2','text_coverage'))
        paths.update({'catalog/r4_normal/A04_net_interest_margin.md',
            'catalog/r4_v2/A04_net_interest_margin.md','catalog/table_task_contracts.json',
            'config/r4_task_contracts_v2.json','docs/evidence/issue_28_prb_policy_revision.json',
            'config/normal_fiscal_year_labels_v1.json','catalog/r6/text_results_v2_policy.json'})
        # The existing task-catalog inspector actually compiles all six
        # retained task Specs before selecting NIM; no authority recursion.
        paths.update('catalog/r4_v2/'+name+'.md' for name in (
            'A03_liquidity_coverage_ratio','A09_nonperforming_loan_ratio',
            'A11_assets_under_management','A12_trading_exposure','A13_geographic_exposure'))
    if metric == 'D04' and not supplied_case:
        # Only the default dispatch uses this current saved-response route.
        # Supplied producers name their actual dependencies in processing_files;
        # a supplied current producer may still declare this same complete set.
        from .ordinary_d04_saved_route import processing_paths
        paths.update(processing_paths())
    from .ordinary_registry_scope import registered_company_row
    # The producer validates the entire program registry's profile mapping.
    # Keep that admission check before reuse; valid unrelated rows still do
    # not become comparison inputs. Source registries use program-side rules.
    from .traits import repository_company_traits
    repository_company_traits(repo_root=ROOT,company_id=company)
    paths.discard('config/company_registry.csv')
    paths.add('scripts/vnext/ordinary_registry_scope.py')
    from .ordinary_saved_result import selected_case_registration
    selected = selected_case_registration(metric)
    registration = {'call_style':'supplied_case'} if supplied_case else selected
    if not supplied_case:
        paths.add('scripts/'+selected['module'].replace('.','/')+'.py')
    return {'company_id':company,'metric_id':metric,'source_root':str(source),
            'saved_result_registration':registration,
        'processing_files':{p:sha256_file(path=ROOT/p) for p in sorted(paths)},
        'company_registry_rows':{
            'program':registered_company_row(repo_root=ROOT,company_id=company),
            'source':registered_company_row(repo_root=source,company_id=company)},
        'provider_enabled':False,'sec_fetch_enabled':False}


def _same_processing_configuration(previous, current):
    """Source checking/control versions are recorded, not extraction inputs.

    These control/checking modules do not select, interpret or calculate a
    metric. Source checks run again before every reuse. Producer/parser/Spec/prompt,
    registry and actual source differences remain part of the comparison.
    """
    checking = {'scripts/vnext/ordinary_current_update.py',
                'scripts/vnext/request_bindings.py',
                'scripts/vnext/ordinary_update_compatibility.py',
                'scripts/vnext/ordinary_result_registration.py'}
    def business(config):
        return {**config,'processing_files':{path:digest for path,digest in config.get('processing_files',{}).items()
                                            if path not in checking}}
    return business(previous)==business(current)


def _current_sources(source, proofs):
    from sec_http import request_log_attempt_id
    from .request_bindings import validate_request_attempt_bindings
    log_digest = sha256_file(path=source/'evidence/requests_log.csv')
    latest = {row['source_url']:(i,row) for i,row in enumerate(_rows(source)) if row['method']=='GET'}
    rows, requests = [], []
    for old in proofs:
        current=latest.get(old['source_url'])
        _need(current is not None,'CURRENT_UPDATE_SOURCE_MISSING:'+old['source_url'])
        index,row=current
        _need(row['status_code']=='200' and not row['error'],'LATEST_SOURCE_REQUEST_FAILED:'+old['source_url'])
        # Pin the actual latest row. Repeated identical legacy GETs are valid,
        # but the convenience selector deliberately cannot disambiguate them.
        # This verifier still checks that row's exact body and header bytes.
        requests.append(dict(source_url=old['source_url'],accession=old['accession'],
            document_name=row['document_name'],content_sha256=row['content_sha256'],
            request_attempt_id=request_log_attempt_id(row_index=index,row=row),require_immutable=False))
        rows.append({'source_url':old['source_url'],'accession':old['accession'],
                     'document_name':row['document_name'],'content_sha256':row['content_sha256']})
    validate_request_attempt_bindings(repo_root=source,requests=requests,expected_log_sha256=log_digest)
    return rows


def _source_census(source, company):
    """Keep newly acquired company files and failures visible, including events."""
    from .annual_sources import _rows
    ciks = set(repository_company_ciks(repo_root=source,company_id=company))
    latest = {}
    for row in _rows(source):
        path = urlsplit(row['source_url']).path
        archive = re.search(r'/data/(\d+)/',path)
        metadata = re.search(r'CIK(\d+)(?:[.-])',path)
        found = archive or metadata
        if row['method']=='GET' and found and str(int(found.group(1))) in ciks:
            latest[row['source_url']] = {k:row[k] for k in ('source_url','status_code','error','content_sha256','document_name')}
    return [latest[url] for url in sorted(latest)]


def _recover(root):
    """Incomplete checks cannot look complete; finish a saved pointer commit."""
    pointer = root/'current-result.json'
    current = strict_json_file(path=pointer) if pointer.is_file() else None
    ready = []
    for path in (root/'checks').glob('*/intent.json'):
        intent = strict_json_file(path=path); terminal = path.with_name('terminal.json')
        if not terminal.is_file():
            _write(terminal,{'status':'INTERRUPTED','attempt_id':intent['attempt_id'],
                            'previous_result':intent['previous_result'],'new_calls':{'provider':0,'paid':0,'sec':0}})
        else:
            report = strict_json_file(path=terminal)
            if report['status']=='CANDIDATE_READY' and report.get('completed_state'):
                ready.append((intent,report))
    while True:
        following = [(i,r) for i,r in ready if i['previous_result']==current
                     and r['completed_state']!=current]
        if not following: break
        _need(len(following)==1,'CURRENT_UPDATE_JOURNAL_BRANCH')
        intent,report=following[0]; state=report['completed_state']
        saved=read_saved_result(output_root=root/'results'/state['version'])
        _need(saved['result']['result_id']==state['result_id']
              and saved['manifest']['company_id']==state['company_id']
              and saved['manifest']['metric_id']==state['metric_id'],'CURRENT_UPDATE_RECOVERY_RECORD_CHANGED')
        _write(pointer,state);current=state;ready.remove((intent,report))
    return current


def _recover_completed_check(root):
    """Recover a finished conclusion separately from the last good result."""
    pointer=root/'completed-check.json'
    current=strict_json_file(path=pointer) if pointer.is_file() else None
    pending=[]
    for path in (root/'checks').glob('*/intent.json'):
        terminal=path.with_name('terminal.json')
        if terminal.is_file():
            report=strict_json_file(path=terminal)
            if report.get('completed_check') is not None:
                pending.append((strict_json_file(path=path),report))
    while True:
        following=[(i,r) for i,r in pending if i.get('previous_check')==current
                   and r['completed_check']!=current]
        if not following:break
        _need(len(following)==1,'CURRENT_UPDATE_COMPLETED_CHECK_BRANCH')
        intent,report=following[0];state=report['completed_check']
        saved=read_saved_result(output_root=root/'results'/state['version'])
        expected='PUBLISHED' if state['status']=='CANDIDATE_READY' else 'WITHHELD'
        _need(state['status'] in {'CANDIDATE_READY','CANDIDATE_WITHHELD'}
              and saved['result']['publication']==expected
              and saved['result']['result_id']==state['result_id']
              and saved['manifest']['company_id']==state['company_id']
              and saved['manifest']['metric_id']==state['metric_id'],
              'CURRENT_UPDATE_COMPLETED_CHECK_RECORD_CHANGED')
        _write(pointer,state);current=state;pending.remove((intent,report))
    return current


def run_once(*, state_root, source_root, company_id, metric_id, shared_input_root=None,
             fiscal_year=None, case_factory=None, processing_files=(), processing_inputs=(),
             current_case_factory=None):
    """One current deterministic update; identical raw input never calculates."""
    _need(current_case_factory is None or callable(current_case_factory)
          and fiscal_year is None and case_factory is None,
          'CURRENT_UPDATE_CURRENT_FACTORY_SCOPE_INVALID')
    _need(metric_id in SAVED_METRIC_IDS or metric_id in EXPLICIT_CASE_METRICS
          and (fiscal_year is not None and callable(case_factory)
               or callable(current_case_factory)), 'CURRENT_UPDATE_METRIC_UNSUPPORTED')
    _need(fiscal_year is None or type(fiscal_year) is int and 1900<=fiscal_year<=9998,
          'CURRENT_UPDATE_REQUESTED_FISCAL_YEAR_INVALID')
    _need(fiscal_year is None or callable(case_factory), 'CURRENT_UPDATE_SELECTED_PERIOD_REQUIRES_CASE_FACTORY')
    _need(fiscal_year is not None or case_factory is None, 'CURRENT_UPDATE_CASE_FACTORY_REQUIRES_FISCAL_YEAR')
    root,source = Path(state_root).resolve(),Path(source_root).resolve()
    if fiscal_year is not None:
        root = root/'periods'/('FY'+str(fiscal_year))
    _need(root != source and root not in source.parents and source not in root.parents,
          'CURRENT_UPDATE_STATE_SOURCE_OVERLAP')
    root.mkdir(parents=True,exist_ok=True)
    with (root/'update.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        _need(not (root/'configuration.json').exists(), 'CURRENT_UPDATE_OLD_NATIVE_HISTORY_REQUIRES_ORIGINAL_CONTROLLER')
        pointer = root/'current-result.json'
        previous = _recover(root)
        completed = _recover_completed_check(root)
        comparison = completed or previous
        if completed:
            _need(completed['company_id']==company_id and completed['metric_id']==metric_id,
                  'CURRENT_UPDATE_WRONG_COMPLETED_COORDINATE')
        if previous:
            _need(previous['company_id']==company_id and previous['metric_id']==metric_id,
                  'CURRENT_UPDATE_WRONG_HISTORY_COORDINATE')
        identity = uuid4().hex; attempt = root/'checks'/identity
        _write(attempt/'intent.json',{'attempt_id':identity,'company_id':company_id,'metric_id':metric_id,
                                    'previous_result':previous,'previous_check':completed})
        try:
            configuration = (_configuration(source,company_id,metric_id,supplied_case=True)
                if case_factory is not None or current_case_factory is not None
                else _configuration(source,company_id,metric_id))
            _need(type(processing_files) in (list,tuple) and len(processing_files)==len(set(processing_files)),
                  'CURRENT_UPDATE_PROCESSING_FILES_INVALID')
            extra = {}
            for relative in processing_files:
                _need(type(relative) is str and not Path(relative).is_absolute()
                      and '..' not in Path(relative).parts, 'CURRENT_UPDATE_PROCESSING_FILE_PATH_INVALID')
                from .sources import resolve_repository_file
                path = resolve_repository_file(repo_root=ROOT,repo_relative_path=relative)
                extra[relative]=sha256_file(path=path)
            if extra:configuration={**configuration,'declared_processing_files':extra}
            if current_case_factory is not None:
                producer_path = inspect.getsourcefile(current_case_factory)
                _need(producer_path is not None, 'CURRENT_UPDATE_CASE_PRODUCER_VERSION_UNAVAILABLE')
                configuration = {**configuration, 'current_case_producer':{
                    'module':current_case_factory.__module__, 'name':current_case_factory.__qualname__,
                    'sha256':sha256_file(path=Path(producer_path))}}
            _need(type(processing_inputs) in (list,tuple), 'CURRENT_UPDATE_PROCESSING_INPUTS_INVALID')
            inputs = {}
            for input_path in processing_inputs:
                path = Path(input_path)
                _need(path.is_absolute() and path.is_file(), 'CURRENT_UPDATE_PROCESSING_INPUT_MISSING')
                path = path.resolve()
                _need(root != path and root not in path.parents,
                      'CURRENT_UPDATE_PROCESSING_INPUT_STATE_OVERLAP')
                inputs[str(path)] = sha256_file(path=path)
            _need(len(inputs)==len(processing_inputs), 'CURRENT_UPDATE_PROCESSING_INPUT_DUPLICATE')
            if inputs:configuration={**configuration,'saved_processing_inputs':inputs}
            if fiscal_year is not None:
                producer_path = inspect.getsourcefile(case_factory)
                _need(producer_path is not None, 'CURRENT_UPDATE_CASE_PRODUCER_VERSION_UNAVAILABLE')
                configuration = {**configuration, 'requested_fiscal_year':fiscal_year,
                    'case_producer':{'module':case_factory.__module__, 'name':case_factory.__qualname__,
                                     'sha256':sha256_file(path=Path(producer_path))}}
            census = _source_census(source,company_id)
            source_errors = [r for r in census if r['status_code']!='200' or r['error']]
            if comparison:
                saved = read_saved_result(output_root=root/'results'/comparison['version'])
                if metric_id == 'E01' and fiscal_year is not None:
                    _need(current_e01_scope(saved),'CURRENT_UPDATE_E01_SAVED_SCOPE_NOT_CONTENT_CONFIRMED')
                _need(saved['manifest']['company_id']==company_id and saved['manifest']['metric_id']==metric_id,
                      'CURRENT_UPDATE_SAVED_COORDINATE_CHANGED')
                _need(saved['result']['result_id']==comparison['result_id'],
                      'CURRENT_UPDATE_COMPLETED_RESULT_ID_CHANGED')
                current = _current_sources(source,saved['manifest']['source_proofs'])
                old = comparison.get('compared_source_proofs') or [{k:p[k] for k in ('source_url','accession','document_name','content_sha256')}
                       for p in saved['manifest']['source_proofs']]
                from .ordinary_update_compatibility import compatible_configuration
                same_processing = _same_processing_configuration(comparison['configuration'], configuration)
                from .ordinary_result_registration import same_registered_processing
                registration_compatible = not same_processing and same_registered_processing(
                    comparison['configuration'],configuration,saved['manifest'],ROOT)
                compatible = registration_compatible or (not same_processing and compatible_configuration(
                    comparison['configuration'], configuration))
                parsed_equivalent=False
                if (metric_id=='D04' and fiscal_year is None
                        and configuration==comparison['configuration'] and not source_errors
                        and (current!=old or census!=comparison.get('source_census'))
                        and {r['source_url'] for r in census}=={r['source_url'] for r in comparison.get('source_census',[])}):
                    old_task=saved.get('input_assessments',{}).get('d04_task_input')
                    if old_task is not None:
                        from .ordinary_d04_task_input import fingerprint,same_task
                        try:
                            new_task=fingerprint(source_root=source,company_id=company_id)
                        except ValueError:
                            # Comparison failure is not a successful conclusion;
                            # the original complete processor handles/records it.
                            new_task=None
                        parsed_equivalent=new_task is not None and same_task(old_task,new_task)
                if ((same_processing or compatible)
                        and ((census==comparison.get('source_census') and current==old) or parsed_equivalent)):
                    status=('PREVIOUS_INPUT_WITHHELD' if saved['result']['publication']=='WITHHELD'
                            else 'NO_SOURCE_CONTENT_CHANGE')
                    report = {'status':status,'attempt_id':identity,
                        'version':comparison['version'],'result_id':saved['result']['result_id'],
                        'result_root':str(root/'results'/comparison['version']),
                        'result_reason_code':saved['result'].get('reason_code'),
                        'raw_input_unchanged':True,'calculation_performed':False,'new_candidate_created':False,
                        'source_check_versions':{path:configuration.get('processing_files',{}).get(path)
                            for path in ('scripts/vnext/ordinary_current_update.py','scripts/vnext/request_bindings.py',
                                         'scripts/vnext/ordinary_update_compatibility.py','scripts/vnext/ordinary_result_registration.py')},
                        'source_observation_errors':source_errors,
                        'new_calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
                    if fiscal_year is not None:report['requested_fiscal_year']=fiscal_year
                    if parsed_equivalent:
                        report['raw_input_unchanged']=False
                        report['task_input_unchanged']=True
                        report['source_comparison']='PARSED_D04_TASK_INPUT_UNCHANGED'
                        # Keep the original Result and citations; only this
                        # completed comparison advances to current raw inputs.
                        report['completed_check']={**comparison,'source_census':census,
                            'compared_source_proofs':current}
                    if compatible:
                        # A new check can recognize the same inputs; the old
                        # result, terminal and last success keep their identities.
                        report['configuration_compatibility'] = (
                            'INLINE_TO_SELECTED_REGISTRATION' if registration_compatible
                            else 'FINITE_INSPECTED_E01_DISPATCH_ONLY' if metric_id=='E01'
                            else 'FINITE_D04_DISPATCH_ONLY')
                        report['completed_check'] = {**comparison, 'configuration':configuration,
                            'status':('CANDIDATE_WITHHELD' if status=='PREVIOUS_INPUT_WITHHELD'
                                      else 'CANDIDATE_READY')}
                    _write(attempt/'terminal.json',report)
                    if compatible or parsed_equivalent:_write(root/'completed-check.json', report['completed_check'])
                    _write(root/'latest-check.json',report)
                    return {k:v for k,v in report.items() if k != 'completed_check'}
            # Full selection/period/subject checks only run for changed/new
            # input. A newly selected filing necessarily changes submissions.
            version = uuid4().hex
            if current_case_factory is not None:
                case = current_case_factory(repo_root=source, company_id=company_id, metric_id=metric_id)
                saved = save_calculated_case(source_root=source,output_root=root/'results'/version,
                    company_id=company_id,metric_id=metric_id,case=case,shared_input_root=shared_input_root)
            elif fiscal_year is None:
                saved = create_saved_result(source_root=source,output_root=root/'results'/version,
                    company_id=company_id,metric_id=metric_id, shared_input_root=shared_input_root)
            else:
                case = case_factory(repo_root=source, company_id=company_id, metric_id=metric_id,
                                    fiscal_year=fiscal_year)
                if metric_id == 'E01':
                    _need(case.get('spec_paths',{}).get('E01') == CURRENT_E01_SPEC_PATH,
                          'CURRENT_UPDATE_E01_CONTENT_SPEC_REQUIRED')
                _need(case['target_period']['fiscal_year']==fiscal_year,
                      'CURRENT_UPDATE_CASE_FISCAL_YEAR_CHANGED')
                saved = save_calculated_case(source_root=source,output_root=root/'results'/version,
                    company_id=company_id,metric_id=metric_id,case=case,shared_input_root=shared_input_root)
            if previous:
                _need(saved['result']['period_end']>=previous['period_end'], 'CURRENT_UPDATE_PERIOD_REGRESSED')
            state={'company_id':company_id,'metric_id':metric_id,'version':version,
                   'period_end':saved['result']['period_end'],'configuration':configuration,
                   'result_id':saved['result']['result_id'],'source_census':census}
            if fiscal_year is not None:state['requested_fiscal_year']=fiscal_year
            report={'status':'CANDIDATE_READY' if saved['result']['publication']=='PUBLISHED' else 'CANDIDATE_WITHHELD',
                    'attempt_id':identity,'version':version,'result_id':saved['result']['result_id'],
                    'result_root':str(root/'results'/version),'calculation_performed':True,'new_candidate_created':True,
                    'result_reason_code':saved['result'].get('reason_code'),
                    'source_observation_errors':source_errors,
                    'new_calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
            if fiscal_year is not None:report['requested_fiscal_year']=fiscal_year
            if report['status']=='CANDIDATE_READY': report['completed_state']=state
            report['completed_check']={**state,'status':report['status']}
            _write(attempt/'terminal.json',report)
            if report['status']=='CANDIDATE_READY': _write(pointer,state)
            _write(root/'completed-check.json',report['completed_check'])
            _write(root/'latest-check.json',report)
            return {k:v for k,v in report.items() if k not in {'completed_state','completed_check'}}
        except Exception as error:
            report={'status':'INPUT_OR_EXECUTION_FAILED','attempt_id':identity,
                    'error_type':type(error).__name__,'reason':str(error),'previous_result':previous,
                    'new_calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
            if fiscal_year is not None:report['requested_fiscal_year']=fiscal_year
            if getattr(error,'category',None) is not None:report['error_category']=error.category
            if not (attempt/'terminal.json').exists():_write(attempt/'terminal.json',report)
            _write(root/'latest-check.json',report); return report

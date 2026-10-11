"""Common B01/B03 computation after current or historical source selection.

Callers select verified saved sources and an actual period. This function reads
CompanyFacts itself and uses installed Specs, the same Calculator and existing
native revenue/D&A/contract-scope checks. It performs no period selection,
acquisition, result storage, or acceptance decision outside those checks.
"""
from .batch_workflow import _structured_concepts
from .calculator import calculate_metric, withheld_metric_result
from .sources import companyfacts_structured_facts
from .deterministic_router import adapt_companyfacts
from .zero_ai_r2 import _exact_filing_source_set
from .xbrl_namespace_policy import YEAR_ONLY


def revenue_admission(*, primary, annual, approved_concepts, contract='components-v1',
                       fiscal_label_resolution=None, allow_single_revenue_line=False, xml=None,
                       namespace_policy=None, annual_period_reader=None):
    """Select source proof and its matching mechanical checks before calculation.

    Only absence of a proven direct total permits the existing component
    path. A source, scope or period error must remain an error, never a fallback.
    """
    from .normal_zero_ai_results import _need
    from .selected_revenue_scope_v1 import selected_revenue_scope, admit_revenue_facts, verify_revenue_observations
    _need(contract in {'components-v1','reported-total-v2'}, 'NORMAL_ZERO_AI_REVENUE_SCOPE_CONTRACT_INVALID')
    options = {}
    if xml is not None: options['xml'] = xml
    if namespace_policy is not None: options['namespace_policy'] = namespace_policy
    if annual_period_reader is not None: options['annual_period_reader'] = annual_period_reader
    if contract == 'reported-total-v2':
        from .selected_reported_revenue_v2 import reported_revenue_scope, admit_reported_revenue_facts, verify_reported_revenue_observations
        scope = reported_revenue_scope(primary=primary, annual=annual, approved_concepts=approved_concepts,
                                       fiscal_label_resolution=fiscal_label_resolution,
                                       allow_single_revenue_line=allow_single_revenue_line, **options)
        if scope['reported_totals']:
            return scope, admit_reported_revenue_facts, verify_reported_revenue_observations
    scope = selected_revenue_scope(primary=primary, annual=annual, approved_concepts=approved_concepts, **options)
    return scope, admit_revenue_facts, verify_revenue_observations


def calculate_selected_income(*, repo_root, prepared, inventory, primary_source,
        facts_source, metric_id, spec, dependency_specs, target, period, traits,
        validate_depreciation_scope=False, validate_revenue_scope=False,
        revenue_scope_contract='components-v1', allow_single_revenue_line=False,
        xml_source=None, namespace_policy=YEAR_ONLY, annual_period_reader=None):
    """Internal computation seam; no caller-supplied monetary operands."""
    from .normal_zero_ai_results import _need
    _need(metric_id in {'B01','B03'}, 'NORMAL_ZERO_AI_SELECTED_INCOME_METRIC_INVALID')
    _need(spec['compiled']['metric_id'] == metric_id, 'NORMAL_ZERO_AI_SELECTED_INCOME_SPEC_INVALID')
    _need(revenue_scope_contract in {'components-v1','reported-total-v2'}
          and (validate_revenue_scope or revenue_scope_contract=='components-v1'),
          'NORMAL_ZERO_AI_REVENUE_SCOPE_CONTRACT_INVALID')
    _need(type(allow_single_revenue_line) is bool and (not allow_single_revenue_line
          or validate_revenue_scope and revenue_scope_contract=='reported-total-v2'),
          'NORMAL_ZERO_AI_SINGLE_REVENUE_OPTION_INVALID')
    dependency_records = []
    revenue_scope = depreciation_scope = None
    manifest = _exact_filing_source_set(company_id=prepared['company_id'], source_role='companyfacts',
        reference=facts_source['source_reference'], inventory_reference=inventory['source_reference'],
        inventory_bytes=inventory['raw_bytes'])
    source_sets = [manifest]
    approved = sorted(set(_structured_concepts(compiled_spec=spec)) | {
        concept for dependency in dependency_specs.values()
        for concept in _structured_concepts(compiled_spec=dependency)})
    facts = companyfacts_structured_facts(raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
        approved_concepts=approved, allowed_ciks=[prepared["entity"]], include_instant=False)
    claims = adapt_companyfacts(raw_bytes=facts_source["raw_bytes"], source_reference=facts_source["source_reference"],
        source_set_manifest=manifest, approved_concepts=approved, allowed_ciks=[prepared["entity"]], include_instant=False)
    if validate_revenue_scope:
        revenue_spec = dependency_specs.get('B01', spec)
        revenue_concepts = revenue_spec['compiled']['inputs']['revenue']['structured_role']['approved_concepts']
        revenue_scope, admit_revenue_facts, verify_revenue_observations = revenue_admission(
            primary=primary_source, annual=prepared.get('original_input',prepared),
            approved_concepts=revenue_concepts, contract=revenue_scope_contract,
            fiscal_label_resolution=prepared.get('fiscal_year_label_resolution'),
            allow_single_revenue_line=allow_single_revenue_line, xml=xml_source,
                namespace_policy=namespace_policy, annual_period_reader=annual_period_reader)
        facts = admit_revenue_facts(facts=facts, scope=revenue_scope)
    execution_target = {**target,"entity":prepared["entity"],"accession":prepared["filing"]["accessionNumber"]}
    reusable = []
    for dependency in dependency_specs.values():
        dep_result, dep_trace, dep_observations = calculate_metric(compiled_spec=dependency,
            target=execution_target, company_traits=traits, structured_facts=facts, verified_observations=[])
        if revenue_scope is not None:
            verify_revenue_observations(observations=dep_observations, scope=revenue_scope)
        dependency_records.extend([*dep_observations, dep_trace, dep_result])
        reusable.extend(dep_observations)
    result, trace, observations = calculate_metric(compiled_spec=spec,
        target=execution_target, company_traits=traits, structured_facts=facts, verified_observations=reusable)
    if metric_id == 'B03' and validate_depreciation_scope and result['publication'] == 'PUBLISHED' and result['value'] is not None:
        from .ordinary_b03_input_scope import inspect_depreciation_input, DIRECT, WITHHELD_REASON
        from .b03_contract_amortization_scope import assess_current_b03_scope
        try:
            depreciation_scope = inspect_depreciation_input(raw_bytes=primary_source['raw_bytes'],
                entity=prepared['entity'], period=period, observations=observations, namespace_policy=namespace_policy)
            if depreciation_scope['status'] == 'RETAKE':
                original_decision = depreciation_scope
                disproved = set(DIRECT) - {depreciation_scope['concept']}
                eligible = [fact for fact in facts if fact['concept'].split(':')[-1] not in disproved]
                result, trace, observations = calculate_metric(compiled_spec=spec,
                    target=execution_target, company_traits=traits, structured_facts=eligible,
                    verified_observations=reusable)
                depreciation_scope = inspect_depreciation_input(raw_bytes=primary_source['raw_bytes'],
                    entity=prepared['entity'], period=period, observations=observations, namespace_policy=namespace_policy)
                depreciation_scope['retake_decision'] = original_decision
                if depreciation_scope['status'] != 'KEEP':
                    depreciation_scope.update(status='WITHHOLD', reason_code=WITHHELD_REASON,
                        why='ONE_APPROVED_RETAKE_DID_NOT_PROVE_PRIMARY_QUANTITY')
            if depreciation_scope['status'] == 'KEEP':
                existing = assess_current_b03_scope(case={'primary_metric_id':'B03',
                    'results':{'B03':result}, 'observations':observations, 'target_period':period,
                    'source_proofs':prepared['source_proofs']}, data_root=repo_root, namespace_policy=namespace_policy)
                depreciation_scope['existing_scope_check'] = existing
                if existing['blocked']:
                    depreciation_scope.update(status='WITHHOLD', reason_code=WITHHELD_REASON,
                        why=existing['status'])
        except ValueError as error:
            depreciation_scope = {'status':'WITHHOLD','reason_code':WITHHELD_REASON,
                'why':str(error),'error_type':type(error).__name__,
                'category':'SOURCE_SCOPE_OR_IMPLEMENTATION_UNRESOLVED'}
        if depreciation_scope['status'] == 'WITHHOLD':
            depreciation_scope['rejected_observations'] = observations
            result, trace = withheld_metric_result(compiled_spec=spec, target=target, reason_code=WITHHELD_REASON)
            observations = []
    original_checks = []
    if xml_source is not None and observations:
        from .selected_income_source_v1 import native_income_reports
        from .ordinary_income_input import verify_income_observations
        reports = {kind:native_income_reports(source, prepared.get('original_input',prepared),
            approved, namespace_policy=namespace_policy, annual_period_reader=annual_period_reader)
            for kind,source in (('primary',primary_source),('xml',xml_source))}
        original_checks = verify_income_observations({'annual_input':prepared,
            'statement_period':period, 'original_reports':reports}, observations)
    if revenue_scope is not None:
        verify_revenue_observations(observations=observations, scope=revenue_scope)
    selection = {"source_candidate_count":len(facts), "selected_fact_ids":[o["source_binding"]["fact_id"] for o in observations],
        "source_reported_periods":sorted({(f["period_start"],f["period_end"]) for f in facts}), "reason_code":result["reason_code"]}
    return {'claims':claims, 'source_sets':source_sets, 'observations':observations,
        'dependency_records':dependency_records, 'result':result, 'trace':trace,
        'selection':selection, 'revenue_scope':revenue_scope,
        'depreciation_scope':depreciation_scope, 'original_checks':original_checks}

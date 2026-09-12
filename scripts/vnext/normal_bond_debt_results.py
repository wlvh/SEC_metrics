"""Ordinary B06 native records for reconciled bonds and separate finance leases."""
from .b06_bond_leases import POLICY, POLICY_PATH, BondLeaseError, inspect_bond_debt_scope
from .calculator import withheld_metric_result
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_annual_input import _registry_rows
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value
from .normal_candidates import _prepare_b06
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .r5_b06_scope import resolve_financing, validate_partition
from .sources import companyfacts_structured_facts, resolve_repository_file
from .specs import compile_spec_file
from .traits import repository_company_traits


SPEC_PATH = 'catalog/r5/B06_bond_leases_v5.md'
RESOLVER = 'debt_equity_bond_and_separate_lease_v5'
MODEL_ID = 'BOND_CURRENT_NONCURRENT_PLUS_SEPARATE_FINANCE_LEASE'


def _need(condition, reason):
    if not condition: raise ValueError(reason)


def _spec(root):
    for path in [SPEC_PATH,POLICY_PATH]:
        _need(sha256_file(path=resolve_repository_file(repo_root=root,repo_relative_path=path)) == sha256_file(path=ROOT/path),
              'ORDINARY_BOND_DEBT_INSTALLED_AUTHORITY_CHANGED')
    spec = compile_spec_file(path=root/SPEC_PATH,dependency_specs={}); rule = spec['compiled']['quality_rule']
    _need(rule['resolver'] == RESOLVER and rule['source_policy'] == POLICY_PATH
          and rule['source_policy_sha256'] == sha256_file(path=root/POLICY_PATH), 'ORDINARY_BOND_DEBT_SPEC_BINDING_CHANGED')
    original = compile_spec_file(path=root/rule['original_metric_spec'],dependency_specs={})
    _need(rule['original_metric_spec_sha256'] == sha256_file(path=root/rule['original_metric_spec'])
          and all(spec['compiled'][k] == original['compiled'][k] for k in ['metric_id','kind','canonical_unit','reported_unit',
              'applicability','required_claims','inputs','formula','top_level_guards','dependencies']),
          'ORDINARY_BOND_DEBT_ECONOMIC_DEFINITION_CHANGED')
    return spec


def prepare_bond_debt_case(*, repo_root, company_id):
    from .deterministic_router import parse_accession_xbrl_source
    preparation = _prepare_b06(repo_root=repo_root,company_id=company_id)
    original = preparation['input_binding']['prepared_annual_input']; end = original['filing']['reportDate']
    parsed = parse_accession_xbrl_source(raw_bytes=preparation['xml']['raw_bytes'])
    available = {f['qualified_name'].split(':')[-1].casefold() for f in parsed.facts
                 if parsed.contexts[f['context_ref']]['period_end'] == end}
    if not all(local.casefold() in available for local in POLICY['note_concepts'].values()): return None
    spec = _spec(repo_root); rule = spec['compiled']['quality_rule']
    prepared = prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    proofs = list({content_hash(value=p):p for p in [*preparation['input_binding']['source_proofs'],
        *original['source_proofs'],*prepared['source_proofs']]}.values())
    admission = verify_saved_source_proofs(data_root=repo_root,proofs=proofs)
    scope = {'entity_scope':'consolidated'}
    target = {'company_id':company_id,'entity':original['entity'],'accession':original['filing']['accessionNumber'],
              'period_start':end,'period_end':end,'scope':scope,'scope_key':content_hash(value=scope)}
    traits = repository_company_traits(repo_root=repo_root,company_id=company_id); source_proof = None
    try:
        company = next(c for c in _registry_rows(repo_root=repo_root) if c['company_id'] == company_id)
        restricted = set(rule['scope_review_dimension_members'])
        if company['industry_profile'] == 'financial_institution' or any(any(str(m).split(':')[-1] in restricted for m in c['dimensions'].values())
                for c in parsed.contexts.values() if c['period_end'] == end):
            raise BondLeaseError('BOND_LEASE_SEPARATE_BANK_OR_INDUSTRIAL_SCOPE_REQUIRED')
        source_proof = inspect_bond_debt_scope(primary=preparation['primary'],xml=preparation['xml'],prepared=original)
        path = repo_root/rule['debt_set_registry']; _need(sha256_file(path=path) == rule['debt_set_registry_sha256'],
                                                         'ORDINARY_BOND_DEBT_REGISTRY_CHANGED')
        registry = strict_json_file(path=path); model = registry['debt_set_models'][MODEL_ID]
        validate_partition(model,registry['required_liability_classes']['consolidated_nonbank'])
        from .b06_disclosure import _facts
        from .constraints import evaluate_expression
        from decimal import Decimal
        get = _facts(preparation['xml']['raw_bytes'],preparation['xml']['source_reference'],target,original['filing']['filingDate'])
        selected = {}; precision = []
        for role,concept in {**model['inputs'],'equity':rule['equity_concept']}.items():
            fact,evidence = get(concept); selected[role] = fact; precision.append(evidence)
        checks = []
        for check in model['checks']:
            values = {k:Decimal(v['value']) for k,v in selected.items()}; extra = []
            for role,concept in check['inputs'].items():
                f,p = get(concept); values[role] = Decimal(f['value']); extra.append(f); precision.append(p)
            left = evaluate_expression(expression=check['left'],values=values)
            right = evaluate_expression(expression=check['right'],values=values)
            _need(left == right,'ORDINARY_BOND_DEBT_DECLARED_RECONCILIATION_FAILED')
            checks.append({'rule':check,'left_value':str(left),'right_value':str(right),'facts':extra})
        amount = evaluate_expression(expression=model['expression'],values={k:Decimal(f['value']) for k,f in selected.items()})
        _need(amount == Decimal(source_proof['proven_composition_amount']),'ORDINARY_BOND_DEBT_PROVED_AMOUNT_CHANGED')
        measurement = {'model_id':MODEL_ID,'model':model,'scope_class':'consolidated_nonbank','complete':True,'unresolved':[],
            'calculation_facts':list(selected.values()),'equity_fact':selected['equity'],
            'components':{k:v for k,v in selected.items() if k!='equity'},'carrying_amount':str(amount),
            'precision':precision,'reconciliations':checks,'debt_scope_definition':registry['debt_scope_definition'],'source_proof':source_proof}
        concepts = sorted({p['concept'] for p in precision}); source = preparation['facts']
        facts = companyfacts_structured_facts(raw_bytes=source['raw_bytes'],source_reference=source['source_reference'],
            approved_concepts=concepts,allowed_ciks=[original['entity']],include_instant=True)
        for p in precision:
            if not p['concept'].startswith('us-gaap:'): continue
            current = [f for f in facts if f['concept']==p['concept'] and f['accession']==target['accession']
                       and f['period_start']==f['period_end']==end and f['entity']==target['entity']]
            _need(current and all(f['unit']=='USD' and f['value'] in {v['value'] for v in p['all_reports']} for f in current),
                  'ORDINARY_BOND_DEBT_COMPANYFACTS_CONFLICT_OR_MISSING:'+p['concept'])
        result,trace,observations,audit = resolve_financing(spec=spec,target=target,traits=traits,facts=facts,measurement=measurement)
        selection = {'classification':'SOURCE_RECONCILED_BONDS_AND_SEPARATE_FINANCE_LEASES','audit':audit}
    except BondLeaseError as error:
        simple_target = {k:target[k] for k in ['company_id','period_start','period_end','scope','scope_key']}
        result,trace = withheld_metric_result(compiled_spec=spec,target=simple_target,reason_code='B06_SOURCE_RELATIONSHIP_UNRESOLVED')
        observations = []; selection = {'classification':'SOURCE_OR_RELATIONSHIP_UNRESOLVED','reason':str(error)}
    records = preparation['records']
    binding = exact_json_value({'record_type':'ORDINARY_BOND_DEBT_INPUT','original_source_input':preparation['input_binding'],
        'annual_label_input':prepared,'source_proofs':proofs,'source_proof':source_proof,'selection':selection,
        'policy_sha256':sha256_file(path=repo_root/POLICY_PATH),'production_authorized':False})
    return {'kind':'STRUCTURED','primary_metric_id':'B06','input_binding':binding,'source_records':records,
        'references':[r for r in records if r['record_type']=='SOURCE_REFERENCE'],'source_proofs':proofs,'admission':admission,
        'spec_paths':{'B06':SPEC_PATH},'compiled_specs':{'B06':spec},'target_period':{'fiscal_year':prepared['table_input']['target_period']['fiscal_year'],
        'period_start':end,'period_end':end},'expected_records':[*records,*observations,trace,result],
        'results':{'B06':result},'traces':{'B06':trace},'observations':observations,'selection':selection}

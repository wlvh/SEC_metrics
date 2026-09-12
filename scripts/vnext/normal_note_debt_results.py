"""Native ordinary B06 records for the explicit no-finance-lease note grammar."""
from .b06_note_carrying import POLICY, POLICY_PATH, NoteCarryingError, inspect_note_carrying, matches_source_grammar
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


SPEC_PATH = 'catalog/r5/B06_note_carrying_v4.md'
RESOLVER = 'debt_equity_note_carrying_v4'


def _need(condition, reason):
    if not condition: raise ValueError(reason)


def _spec(root):
    for path in [SPEC_PATH,POLICY_PATH]:
        _need(sha256_file(path=resolve_repository_file(repo_root=root,repo_relative_path=path)) == sha256_file(path=ROOT/path),
              'ORDINARY_NOTE_DEBT_INSTALLED_AUTHORITY_CHANGED')
    spec = compile_spec_file(path=root/SPEC_PATH,dependency_specs={})
    semantic = spec['compiled']; rule = semantic['quality_rule']
    original = compile_spec_file(path=root/rule['original_metric_spec'],dependency_specs={})
    _need(rule['resolver'] == RESOLVER and rule['source_policy'] == POLICY_PATH
          and rule['source_policy_sha256'] == sha256_file(path=root/POLICY_PATH)
          and rule['original_metric_spec_sha256'] == sha256_file(path=root/rule['original_metric_spec']),
          'ORDINARY_NOTE_DEBT_SPEC_BINDING_CHANGED')
    _need(all(semantic[k] == original['compiled'][k] for k in ['metric_id','kind','canonical_unit','reported_unit',
          'applicability','required_claims','inputs','formula','top_level_guards','dependencies']),
          'ORDINARY_NOTE_DEBT_ECONOMIC_DEFINITION_CHANGED')
    return spec


def prepare_note_debt_case(*, repo_root, company_id):
    """None means a different grammar; a matched but failed grammar stays withheld."""
    preparation = _prepare_b06(repo_root=repo_root,company_id=company_id)
    original = preparation['input_binding']['prepared_annual_input']
    end = original['filing']['reportDate']
    if not matches_source_grammar(preparation['xml']['raw_bytes'],end):
        return None
    spec = _spec(repo_root)
    prepared = prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    proofs = list({content_hash(value=p):p for p in [*preparation['input_binding']['source_proofs'],
        *original['source_proofs'],*prepared['source_proofs']]}.values())
    admission = verify_saved_source_proofs(data_root=repo_root,proofs=proofs)
    scope = {'entity_scope':'consolidated'}
    target = {'company_id':company_id,'entity':original['entity'],'accession':original['filing']['accessionNumber'],
        'period_start':end,'period_end':end,'scope':scope,'scope_key':content_hash(value=scope)}
    traits = repository_company_traits(repo_root=repo_root,company_id=company_id)
    source_proof = None; measurement = None
    try:
        company = next(c for c in _registry_rows(repo_root=repo_root) if c['company_id'] == company_id)
        if company['industry_profile'] == 'financial_institution':
            raise NoteCarryingError('NOTE_CARRYING_SEPARATE_BANK_SCOPE_REQUIRED')
        from .deterministic_router import parse_accession_xbrl_source
        parsed = parse_accession_xbrl_source(raw_bytes=preparation['xml']['raw_bytes'])
        restricted = set(spec['compiled']['quality_rule']['scope_review_dimension_members'])
        if any(any(str(m).split(':')[-1] in restricted for m in c['dimensions'].values())
               for c in parsed.contexts.values() if c['period_end'] == end):
            raise NoteCarryingError('NOTE_CARRYING_SEPARATE_INDUSTRIAL_SCOPE_REQUIRED')
        source_proof = inspect_note_carrying(primary=preparation['primary'],xml=preparation['xml'],prepared=original)
        rule = spec['compiled']['quality_rule']; path = repo_root/rule['debt_set_registry']
        _need(sha256_file(path=path) == rule['debt_set_registry_sha256'], 'ORDINARY_NOTE_DEBT_REGISTRY_CHANGED')
        registry = strict_json_file(path=path); model = registry['debt_set_models'][POLICY['model_id']]
        validate_partition(model,registry['required_liability_classes']['consolidated_nonbank'],absent=['finance_leases'])
        from .b06_disclosure import _facts
        get = _facts(preparation['xml']['raw_bytes'],preparation['xml']['source_reference'],target,original['filing']['filingDate'])
        selected = {}; precision = []
        for role,concept in {**model['inputs'],'equity':rule['equity_concept']}.items():
            fact, evidence = get(concept)
            _need(fact['value'] == source_proof['reports'][role]['chosen']['value'], 'ORDINARY_NOTE_DEBT_LOCATOR_AMOUNT_CHANGED')
            selected[role] = fact; precision.append(evidence)
        total = source_proof['composition']['balances']['total']
        measurement = {'model_id':POLICY['model_id'],'model':model,'scope_class':'consolidated_nonbank',
            'complete':True,'unresolved':[],'established_absent_classes':['finance_leases'],
            'source_credit':'SEPARATE_ORDINARY_BASELINE_ADMISSION',
            'calculation_facts':list(selected.values()),'equity_fact':selected['equity'],
            'components':{k:v for k,v in selected.items() if k != 'equity'},'carrying_amount':total,
            'precision':precision,'debt_scope_definition':registry['debt_scope_definition'],
            'source_proof':source_proof,'reconciliations':source_proof['composition']}
        source = preparation['facts']
        facts = companyfacts_structured_facts(raw_bytes=source['raw_bytes'],source_reference=source['source_reference'],
            approved_concepts=['us-gaap:'+name for name in POLICY['monetary_concepts'].values()],
            allowed_ciks=[original['entity']],include_instant=True)
        for role, name in POLICY['monetary_concepts'].items():
            current = [f for f in facts if f['concept'] == 'us-gaap:'+name and f['accession'] == target['accession']
                       and f['period_start'] == f['period_end'] == end and f['entity'] == target['entity']]
            _need(current and all(f['unit'] == 'USD' and f['value'] == source_proof['reports'][role]['chosen']['value'] for f in current),
                  'ORDINARY_NOTE_DEBT_COMPANYFACTS_CONFLICT_OR_MISSING:'+role)
        result,trace,observations,audit = resolve_financing(spec=spec,target=target,traits=traits,facts=facts,measurement=measurement)
        selection = {'classification':'SOURCE_RECONCILED_NOTE_CARRYING','audit':audit}
    except NoteCarryingError as error:
        result,trace = withheld_metric_result(compiled_spec=spec,target=target,reason_code='B06_SOURCE_RELATIONSHIP_UNRESOLVED')
        observations = []
        selection = {'classification':'SOURCE_OR_RELATIONSHIP_UNRESOLVED','reason':str(error)}
    records = preparation['records']
    binding = exact_json_value({'record_type':'ORDINARY_NOTE_DEBT_INPUT','original_source_input':preparation['input_binding'],
        'annual_label_input':prepared,'source_proofs':proofs,'source_proof':source_proof,'selection':selection,
        'policy_sha256':sha256_file(path=repo_root/POLICY_PATH),'production_authorized':False})
    return {'kind':'STRUCTURED','primary_metric_id':'B06','input_binding':binding,'source_records':records,
        'references':[r for r in records if r['record_type']=='SOURCE_REFERENCE'],
        'source_proofs':proofs,'admission':admission,'spec_paths':{'B06':SPEC_PATH},'compiled_specs':{'B06':spec},
        'target_period':{'fiscal_year':prepared['table_input']['target_period']['fiscal_year'],
                         'period_start':end,'period_end':end},
        'expected_records':[*records,*observations,trace,result],
        'results':{'B06':result},'traces':{'B06':trace},'observations':observations,'selection':selection}

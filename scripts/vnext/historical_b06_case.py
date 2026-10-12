"""Selected historical B06 inputs for the shared public debt computation.

This module selects a saved fiscal year and checks its amendment packet. The public B06 seam owns debt calculation; the company controller owns saving and reuse.
"""
from pathlib import Path
from sec_urls import companyfacts_url, submissions_url
from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .normal_governance_input import _Sources
from .normal_period_selection import resolve_period_selection
from .normal_source_authority import ROOT
from .normal_annual_input_v2 import exact_json_value
from .ordinary_source_authority import verify_ordinary_source_proofs


METRICS = ('B06',)
NOTE_LAYOUT = 'inline-paragraphs-v2'
from .current_b06_case import INLINE_NOTE_PROCESSING_FILES as SHARED_B06_FILES

PROCESSING_FILES = tuple(dict.fromkeys((*SHARED_B06_FILES, *(
    'scripts/vnext/'+name+'.py' for name in (
        'historical_b06_case', 'historical_annual_input', 'historical_dei',
        'historical_fiscal_labels', 'normal_period_selection', 'normal_history_catalog',
        'annual_sources', 'instant_balance_amendment')),
    'config/normal_period_selection_v1.json', 'config/instant_balance_amendment_v1.json')))


class HistoricalDebtInputError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR', *, filing=None):
        super().__init__(reason)
        self.category=category
        self.filing=filing


def prepare_selected_debt_sources(*, repo_root, company_id, fiscal_year):
    source = Path(repo_root)
    selection = resolve_period_selection(repo_root=source, company_id=company_id,
        fiscal_year=fiscal_year, rules_root=ROOT)
    annual = prepare_historical_annual_input(repo_root=source, company_id=company_id,
        period_selection=selection, rules_root=ROOT)
    original = annual['original_input']
    if original['subject_policy']['mode'] != 'CONTINUOUS_PRIMARY':
        raise HistoricalDebtInputError('HISTORICAL_B06_PERIOD_SUBJECT_NOT_RECEIVED',
            'IMPLEMENTATION_GAP', filing=original['filing'])
    reader = _Sources(source, company_id, original['entity'])
    reader.read(submissions_url(cik=int(original['entity'])), role='submissions',
        media_type='application/json')
    facts = reader.read(companyfacts_url(cik=int(original['entity'])),
        accession=original['filing']['accessionNumber'], role='companyfacts',
        media_type='application/json')
    originals = reader.auditor_filing(original['filing'])
    primary = [s for s in originals if s['raw_blob']['media_type']=='text/html']
    xml = [s for s in originals if s['raw_blob']['media_type']=='application/xml']
    if len(primary)!=1 or len(xml)!=1:
        raise ValueError('HISTORICAL_B06_ORIGINAL_SOURCE_SET_AMBIGUOUS')
    body = {'record_type':'NORMAL_B06_INPUT_BINDING','prepared_annual_input':original,
        'source_proofs':[s['proof'] for s in reader.proofs.values()],
        'source_sets':reader.file_sets}
    return {'annual':annual,'selection':selection,'reader':reader,
        'preparation':{'input_binding':{**body,'input_binding_id':content_hash(value=body)},
            'records':list(reader.records.values()),'facts':facts,'primary':primary[0],'xml':xml[0]}}


def prepare_selected_debt_input(*, repo_root, selected):
    """Use existing amendment and B06 property checks on the selected sources."""
    from .annual_amendment_scope import (AmendmentScopeError,
        POLICY_PATH as AMENDMENT_POLICY_PATH)
    from .annual_amendment_scope_v2 import inspect_annual_amendment_scope
    from .b06_current_input import (inspect_current_debt_amendment,
        POLICY_PATH as DEBT_POLICY_PATH, POLICY)
    annual=selected['annual']['original_input']
    reader=selected['reader']
    primary=selected['preparation']['primary']
    def arguments(source,filing):
        return {'raw':source['raw_bytes'],'blob':source['raw_blob'],
            'reference':source['source_reference'],'filing':filing}
    original=arguments(primary,annual['filing'])
    amendments=[arguments(reader.primary(filing),filing)
                for filing in annual['amendments']]
    scopes=[];checks=[]
    for amendment in amendments:
        try:
            scopes.append(inspect_annual_amendment_scope(original=original,amendment=amendment,
                company_id=annual['company_id'],cik=annual['entity'],note_layout=NOTE_LAYOUT))
            checks.append(inspect_current_debt_amendment(original=original,amendment=amendment,
                company_id=annual['company_id'],cik=annual['entity'],note_layout=NOTE_LAYOUT))
        except AmendmentScopeError as error:
            if str(error)!='AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED':raise
            raise HistoricalDebtInputError('HISTORICAL_B06_AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED',
                'IMPLEMENTATION_GAP', filing=amendment['filing']) from error
    proofs=list({content_hash(value=p):p for p in [*annual['source_proofs'],
        *[s['proof'] for s in reader.proofs.values()]]}.values())
    records=list(reader.records.values())
    amendment_packet={'prepared_input':annual,'source_proofs':proofs,
        'source_admission':verify_ordinary_source_proofs(data_root=repo_root,proofs=proofs),
        'scopes':scopes,'source_records':records,
        'policy_sha256':sha256_file(path=ROOT/AMENDMENT_POLICY_PATH),
        'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
    body=exact_json_value({**amendment_packet,'record_type':'B06_CURRENT_INPUT',
        'input_class':POLICY['input_class'],'metric_ids':['B06'],'checks':checks,
        'decision':'INPUT_PROPERTY_PROVEN' if all(c['decision']=='INPUT_PROPERTY_PROVEN'
                                                 for c in checks) else 'WITHHELD',
        'current_primary_only':True,'per_metric_statement_scope_required':True,
        'annual_continuity_proven':False,'debt_completeness_proven':False,
        'policy_sha256':sha256_file(path=ROOT/DEBT_POLICY_PATH),'note_layout':NOTE_LAYOUT})
    return {**body,'current_input_id':content_hash(value=body)}


def prepare_historical_b06_year_case(*, repo_root, company_id, metric_id, fiscal_year):
    if metric_id not in METRICS:
        raise HistoricalDebtInputError('HISTORICAL_B06_METRIC_REQUIRED', 'IMPLEMENTATION_GAP')
    selected = prepare_selected_debt_sources(repo_root=repo_root, company_id=company_id,
                                            fiscal_year=fiscal_year)
    packet = prepare_selected_debt_input(repo_root=repo_root, selected=selected)
    from .current_b06_case import prepare_selected_b06_case
    case = prepare_selected_b06_case(source_root=repo_root, company_id=company_id,
        preparation=selected['preparation'], annual=selected['annual'], packet=packet)
    return {**case, 'historical_period_selection': selected['selection']}

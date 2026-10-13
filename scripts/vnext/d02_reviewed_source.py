"""Pure D02 request and saved-subreview aggregation, without model IO or storage."""
import json
from pathlib import Path

from .canonical import content_hash
from . import legal_review_contract as contract
from .text_business_candidates import _check_document, _excerpt, _substantive, going_concern_candidates
from .governance_signals import _FactAttributes
from .xbrl_namespace_policy import YEAR_ONLY, YEAR_QUARTER_OR_DATE, is_sec_namespace

PROCESSING_FILES=(
    'scripts/vnext/d02_reviewed_source.py',
    'scripts/vnext/d02_text_results_v3.py',
    'scripts/vnext/legal_review_contract.py',
    'scripts/vnext/text_business_candidates.py',
    'scripts/vnext/text_coverage.py',
    'scripts/vnext/historical_annual_input.py',
    'scripts/vnext/historical_dei.py',
    'scripts/vnext/historical_fiscal_labels.py',
    'scripts/vnext/historical_filing_inventory.py',
    'scripts/vnext/normal_period_selection.py',
    'scripts/vnext/normal_history_catalog.py',
    'scripts/vnext/normal_governance_input.py',
    'scripts/vnext/normal_annual_input.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'scripts/vnext/fiscal_year_labels.py',
    'scripts/vnext/xbrl_namespace_policy.py',
    'scripts/vnext/text_results.py',
    'scripts/vnext/text_results_v2.py',
    'scripts/vnext/text_review.py',
    'scripts/vnext/render.py',
    'scripts/vnext/review.py',
    'scripts/vnext/scope_contract.py',
    'scripts/vnext/states.py',
    'scripts/vnext/text_rendering_limits.py',
    'catalog/r6/D02_legal_disclosures_v1.md',
    'catalog/r6/text_business_candidates_v1.json',
    'catalog/r6/text_results_v2_policy.json',
    'config/normal_period_selection_v1.json',
    'config/normal_fiscal_year_labels_v1.json',
)


def _source_sec_namespace_policy(raw_bytes):
    """Select the existing finite policy from resolved original DEI facts.

    Keep annual-only sources on their unchanged old document/request identity.
    A foreign or malformed URI never opts a source into the expanded policy.
    """
    metadata = _FactAttributes(); metadata.feed(raw_bytes.decode('utf-8-sig')); metadata.close()
    expanded = any(is_sec_namespace(fact['concept'][0], taxonomy='dei', namespace_policy=YEAR_QUARTER_OR_DATE)
                   and not is_sec_namespace(fact['concept'][0], taxonomy='dei', namespace_policy=YEAR_ONLY)
                   for fact in metadata.facts.values())
    return YEAR_QUARTER_OR_DATE if expanded else YEAR_ONLY


def prepare_historical_legal_sources(*, repo_root, company_id, fiscal_year):
    """Select one saved annual using the existing historical source boundary."""
    from .normal_source_authority import ROOT
    from .normal_period_selection import resolve_period_selection
    from .historical_annual_input import prepare_historical_annual_input
    from .normal_governance_input import _Sources
    from .ordinary_source_authority import verify_ordinary_source_proofs
    from . import d02_text_results_v3 as core
    root=Path(repo_root)
    selected=resolve_period_selection(repo_root=root,company_id=company_id,
        fiscal_year=fiscal_year,rules_root=ROOT)
    annual=prepare_historical_annual_input(repo_root=root,company_id=company_id,
        period_selection=selected,rules_root=ROOT)
    _need(not annual['amendments'] and annual['subject_policy']['mode']=='CONTINUOUS_PRIMARY',
          'D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED','IMPLEMENTATION_REQUIRED')
    period=annual['table_input']['target_period']
    reader=_Sources(root,company_id,annual['entity'])
    primary=reader.primary(annual['filing']);ref=primary['source_reference'];blob=primary['raw_blob']
    target={'company_id':company_id,'entity':annual['entity'],
        'accession':annual['filing']['accessionNumber'],'period_start':period['period_start'],
        'period_end':period['period_end'],'scope':core.SCOPES['D02']}
    target['scope_key']=content_hash(value=target['scope'])
    arguments={'target':target,'source_references':[ref],
        'raw_blobs':{blob['raw_asset_id']:blob},
        'raw_bytes_by_id':{blob['raw_asset_id']:primary['raw_bytes']},
        'source_filings':{ref['source_reference_id']:annual['filing']},'d02_page_furniture':True}
    namespace_policy = _source_sec_namespace_policy(primary['raw_bytes'])
    if namespace_policy != YEAR_ONLY:
        arguments['namespace_policy'] = namespace_policy
    prepared=core.prepare_business_text_sources(metric_id='D02',**arguments)
    proofs=list({content_hash(value=p):p for p in [*annual['source_proofs'],
        *[value['proof'] for value in reader.proofs.values()]]}.values())
    return {'target_period':period,'period_selection':selected,'prepared_annual_input':annual,
        'source_arguments':arguments,'prepared':prepared,
        'requests':item8_requests(prepared=prepared,target=target),
        'source_proofs':proofs,'references':[ref],'source_records':list(reader.records.values()),
        'admission':verify_ordinary_source_proofs(data_root=root,proofs=proofs),
        'new_provider_execution':False}


class ReviewedLegalSourceError(ValueError):
    def __init__(self, reason, category='SOURCE_INTEGRITY_ERROR'):
        super().__init__(reason)
        self.category=category


def _need(condition, reason, category='SOURCE_INTEGRITY_ERROR'):
    if not condition:
        raise ReviewedLegalSourceError(reason,category)


def item8_requests(*, prepared, target):
    """Build each complete eligible Item8 request from the prepared source.

    Nested referenced notes belong to their own range, and bounded auditor
    reports are outside the registrant's litigation disclosures. A missing
    note-ownership migration is named rather than silently changing the pool.
    """
    _need(prepared.get('metric_id')=='D02','D02_REVIEW_SOURCE_METRIC_CHANGED')
    requests=[]
    for sid,document in prepared['documents'].items():
        _check_document(document)
        _need(document['company_id']==target['company_id']
              and document['source_reference_id']==sid
              and type(target['entity']) is str and target['entity'].isdigit()
              and int(document['cik'])==int(target['entity'])
              and document['period_end']==target['period_end'],
              'D02_REVIEW_DOCUMENT_COORDINATE_CHANGED')
        proposal=prepared['proposals'][sid]
        _need(proposal['document_id']==document['text_document_id']
              and proposal['proposal_id']==content_hash(value={
                  k:v for k,v in proposal.items() if k!='proposal_id'}),
              'D02_REVIEW_SOURCE_PROPOSAL_CHANGED')
        ranges=proposal['checked_ranges']
        scopes=[r for r in ranges if r['section_id']=='ITEM_8']
        _need(len(scopes)==1,'D02_REVIEW_ITEM8_RANGE_NOT_UNIQUE','IMPLEMENTATION_REQUIRED')
        scope=scopes[0]
        for reference in proposal['note_references']:
            for note in reference['range_candidates']:
                if (scope['start_block']<=note['start_block']
                        and note['end_block_exclusive']<=scope['end_block_exclusive']):
                    selection=proposal.get('d02_incorporated_note_scopes', {})
                    declared=note in selection.get('containers', [])
                    scoped=[r for r in selection.get('disclosure_scopes', [])
                            if r['requested_reference']==note['requested_reference']
                            and note['start_block']<=r['start_block']<r['end_block_exclusive']<=note['end_block_exclusive']]
                    _need(any(r['section_id'].startswith('NOTE_')
                              and r['start_block']==note['start_block']
                              and r['end_block_exclusive']==note['end_block_exclusive'] for r in ranges)
                          or declared and scoped and all(r in ranges for r in scoped),
                          'D02_REFERENCED_NOTE_OWNERSHIP_NOT_MIGRATED','IMPLEMENTATION_REQUIRED')
        reports=going_concern_candidates(document=document)['auditor_report_ranges']
        relevant=[r for r in reports if scope['start_block']<=r['start_block']<scope['end_block_exclusive']]
        _need(all(r['status']=='LOCAL_REPORT_RANGE_LOCATED' for r in relevant),
              'D02_REVIEW_AUDITOR_BOUNDARY_NOT_PROVEN','IMPLEMENTATION_REQUIRED')
        audit={i for r in relevant for i in range(r['start_block'],r['end_block_exclusive'])}
        excluded={r['block_index'] for r in proposal.get('d02_page_furniture',{}).get('removed_blocks',[])}
        owner={}
        for r in ranges:
            for i in range(r['start_block'],r['end_block_exclusive']):
                old=owner.get(i)
                if old is None or r['end_block_exclusive']-r['start_block']<old['end_block_exclusive']-old['start_block']:
                    owner[i]=r
        pool=[]
        for i in range(scope['start_block'],scope['end_block_exclusive']):
            if owner[i] is not scope or i in excluded or i in audit:
                continue
            block=document['blocks'][i]
            if _substantive(document,block) or (block['linked'] and _substantive(document,{**block,'linked':False})):
                pool.append(i)
        admitted=sorted(c['block_index'] for c in proposal['D02']['candidates'] if c['section_id']=='ITEM_8')
        _need(set(admitted)<=set(pool),'D02_REVIEW_CANDIDATES_OUTSIDE_ELIGIBLE_POOL','IMPLEMENTATION_REQUIRED')
        if not pool:
            _need(not admitted,'D02_REVIEW_EMPTY_POOL_HAS_ADMISSIONS')
            continue
        requests.append(contract.review_request(company_id=target['company_id'],
            target_cik=target['entity'],period_end=target['period_end'],document=document,
            pool=pool,keyword_admitted=admitted))
    return requests


def apply_saved_reviews(*, prepared, target, reviews):
    """Replace only Item8 using complete matching saved-reader outputs.

    This does not establish the semantic correctness of a model's decisions;
    source and business acceptance remain separately evaluated by the caller.
    Missing or unsettled answers do not yield a partial disclosure set.
    """
    requests=item8_requests(prepared=prepared,target=target)
    _need(type(reviews) is list,'D02_REVIEW_ANSWER_SET_INVALID')
    ids=[r['request_id'] for r in reviews]
    _need(len(ids)==len(set(ids)),'D02_REVIEW_ANSWER_DUPLICATED')
    _need(set(ids)=={r['request_id'] for r in requests},
          'D02_REVIEW_COMPLETE_ANSWER_SET_NOT_AVAILABLE','MODEL_RESPONSE_REQUIRED')
    by_id={r['request_id']:r for r in reviews}
    proposals=dict(prepared['proposals']);coverages=dict(prepared['coverages'])
    for request in requests:
        review=by_id[request['request_id']]
        _need(review.get('record_type')=='SAVED_D02_ITEM8_REVIEW_READ'
              and all(review.get(k)==request[k] for k in (
                  'request_id','source_id','company_id','target_cik','period_end','filing')),
              'D02_REVIEW_CURRENT_REQUEST_DIFFERS')
        raw=json.dumps({'decisions':[{'block_id':k,**v} for k,v in review['decisions'].items()],
            'also_in_scope':[{'block_id':k,**v} for k,v in review['also_in_scope'].items()]})
        decisions,added=contract.validate_answer(request=request,raw_output=raw)
        included,reason,unsettled=contract.reviewed_blocks(request=request,decisions=decisions,added=added)
        _need(included==review['included_block_ids'] and reason==review['withheld_reason']
              and unsettled==review['unsettled_block_ids'],'D02_REVIEW_POSTPROCESSING_DIFFERS')
        if reason:
            raise contract.LegalReviewUnsettled(reason+':'+','.join(unsettled))
        sid=request['filing']['source_reference_id'];document=prepared['documents'][sid]
        proposal=prepared['proposals'][sid];previous=proposal['D02']['candidates']
        counted=[int(i[1:]) for i in included]
        candidates=[]
        for scope in proposal['checked_ranges']:
            if scope['section_id']=='ITEM_8':
                candidates.extend(_excerpt(document,document['blocks'][i],'ITEM_8',[contract.REVIEW_LABEL]) for i in counted)
            else:
                candidates.extend(c for c in previous if c['section_id']==scope['section_id'])
        _need([c for c in previous if c['section_id']!='ITEM_8']
              ==[c for c in candidates if c['section_id']!='ITEM_8'],
              'D02_REVIEW_NON_ITEM8_EXCERPTS_CHANGED')
        selection={'method':'SAVED_ITEM8_REVIEW','contract':request['contract'],
            'request_id':request['request_id'],'counted_blocks':counted,
            'original_execution_id':review['original_execution_id'],
            'original_execution_mode':review['original_execution_mode'],
            'new_provider_execution':False,'semantic_correctness_verified':False}
        body={k:v for k,v in proposal.items() if k!='proposal_id'}
        body['D02']={**proposal['D02'],'candidates':candidates,
            'finding_status':'SOURCE_EXCERPTS_FOUND' if candidates else 'NO_SUPPORTED_SOURCE_LANGUAGE'}
        body['item8_review_selection']=selection
        proposals[sid]={**body,'proposal_id':content_hash(value=body)}
        coverage={k:v for k,v in prepared['coverages'][sid].items() if k!='coverage_hash'}
        coverage['item8_review_selection']=selection
        coverages[sid]={**coverage,'coverage_hash':content_hash(value=coverage)}
    return {**prepared,'proposals':proposals,'coverages':coverages}


def finish_historical_legal_case(*, bundle, reviews):
    """Use the existing text Evidence/Review/Calculator, without persistence.

    Public code supplies verified saved-reader outputs. The source-excerpt
    result makes no case-count, aggregate-liability or legal-absence claim.
    """
    from datetime import datetime,timezone
    from .normal_source_authority import ROOT
    from . import d02_text_results_v3 as core
    from .specs import compile_spec_file
    from .review import (_create_review_decision,_system_approved_claims,
        SYSTEM_REVIEWER_ID,SYSTEM_REVIEW_REASON)
    from .traits import repository_company_traits
    path='catalog/r6/D02_legal_disclosures_v1.md'
    spec=compile_spec_file(path=ROOT/path,dependency_specs={})
    args={**bundle['source_arguments'],'d02_saved_reviews':reviews,'compiled_spec':spec}
    candidate=core.create_deterministic_text_candidate(**args)
    evidence=core.build_text_evidence(candidate=candidate,**args)
    unit,_=core.build_text_review_unit(compiled_spec=spec,candidate=candidate,
        evidence_check=evidence,source_bindings=bundle['references'])
    decision=_create_review_decision(review_unit=unit,decision='APPROVE',
        approved_claims=_system_approved_claims(review_unit=unit),
        required_claims=spec['compiled']['required_claims'],reviewer_type='SYSTEM',
        reviewer_id=SYSTEM_REVIEWER_ID,decided_at_utc=datetime.now(timezone.utc).isoformat(),
        reason=SYSTEM_REVIEW_REASON,supersedes_decision_id=None)
    result,trace,observations=core.replay_text_result(
        company_traits=repository_company_traits(repo_root=ROOT,
            company_id=args['target']['company_id']),candidate=candidate,
        evidence_check=evidence,review_unit=unit,review_decisions=[decision],**args)
    return {'kind':'STRUCTURED','primary_metric_id':'D02',
        'compiled_specs':{'D02':spec},'spec_paths':{'D02':path},
        'target_period':bundle['target_period'],'prepared_annual_input':bundle['prepared_annual_input'],
        'references':bundle['references'],'source_proofs':bundle['source_proofs'],
        'admission':bundle['admission'],'results':{'D02':result},'traces':{'D02':trace},
        'expected_records':[*bundle['source_records'],candidate,evidence,unit,decision,
            *observations,trace,result],
        'input_binding':{'record_type':'HISTORICAL_D02_SAVED_REVIEW_INPUT',
            'period_selection':bundle['period_selection'],
            'prepared_input':bundle['prepared_annual_input'],
            'request_ids':[r['request_id'] for r in bundle['requests']],
            'source_proofs':bundle['source_proofs'],'d02_page_furniture':True,
            'saved_reviews':reviews,'new_provider_execution':False},
        'input_assessments':{'D02':{'complete_item8_answer_set':True,
            'source_excerpts_only':True,'case_count_asserted':False,
            'total_litigation_liability_asserted':False,'legal_absence_asserted':False,
            'model_semantic_correctness_inferred_from_form':False,
            'original_execution_ids':[r['original_execution_id'] for r in reviews],
            'new_provider_execution':False}},
        'selection':{'method':'LEGAL_DISCLOSURE_EXCERPTS_V1_WITH_SAVED_ITEM8',
            'request_ids':[r['request_id'] for r in bundle['requests']],
            'excerpt_count':len(candidate['selected'])},'rules_root':str(ROOT)}

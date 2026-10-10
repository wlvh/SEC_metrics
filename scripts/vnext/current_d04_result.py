"""Complete saved D04 model inputs through the ordinary company record writer.

No model socket, claim or automatic retry exists here. Original call and
receipt identities remain inputs; current source and response checks precede
the established text aggregation.
"""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .canonical import content_hash, strict_json_file, strict_json_loads
from .capacity_utilization_source import need
from .normal_source_authority import ROOT


def require_complete_assessment(assessment):
    """A missing or undecided group cannot be a company-level conclusion."""
    need(assessment['all_source_requests_accepted'] is True
         and not assessment['missing_request_ids'] and not assessment['failed_requests']
         and [r['request_id'] for r in assessment['completed']] == assessment['required_request_ids']
         and assessment['proposed_branch'] in {'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW',
            'TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW'},
         'D04_COMPLETE_SAVED_RESPONSE_SET_REQUIRED')
    for row in assessment['completed']:
        selected=row['candidate']['selected']['source_assessment']
        need(row['evidence']['status']=='PASS'
             and not row['candidate'].get('unresolved_competing_claims')
             and not any(f.get('kind')=='UNRESOLVED' or f.get('subject')=='UNRESOLVED'
                 or f.get('timing')=='UNRESOLVED' for f in selected['findings']),
             'D04_SAVED_RESPONSE_UNRESOLVED')


def prepare_current_d04_case(*, source_root, company_id, ledger=None):
    from . import continuous_semantic_calls as calls
    from .continuous_call_ledger import CallLedger, _FACTORY
    from .current_request_configuration import load_current_configuration
    from .capacity_update_input import source_equivalence
    from .capacity_native_assessment import collect_native_assessments
    from .native_unit_index import validate_request_partition
    source_root=Path(source_root)
    configuration=load_current_configuration(repo_root=ROOT)
    if ledger is None:
        root=Path(configuration['policy']['budget_root'])
        ledger=CallLedger(factory=_FACTORY,root=root,
            binding=strict_json_file(path=root/'binding.json'),live=True)
    current=calls.prepare_requests(company_id=company_id,metric_id='D04',native=True,
        reference_context=True,complete_response_contract=True,
        source_root=source_root,source_ledger=ledger)
    template=current[0];current_source=strict_json_loads(text=template.source_bytes.decode())
    with ledger.locked():
        rows=ledger.snapshot()['rows']
    sources={}
    for row in rows:
        if row['channel']!='PROVIDER' or row['status']!='SUCCEEDED':continue
        path=ledger.root/'calls'/('%04d'%row['ordinal'])
        if not (path/'source.json').exists():continue
        source=strict_json_file(path=path/'source.json')
        if source.get('company_id')!=company_id or source.get('metric_id')!='D04':continue
        try:equivalence=source_equivalence(current=current_source,original=source)
        except ValueError:continue
        sources.setdefault(source['semantic_source_id'],(source,equivalence))
    need(len(sources)==1,'D04_SAVED_COMPANY_SOURCE_MISSING_OR_AMBIGUOUS')
    source,equivalence=next(iter(sources.values()))
    requests={}
    for row in rows:
        if row['channel']!='PROVIDER':continue
        path=ledger.root/'calls'/('%04d'%row['ordinal'])
        if not (path/'semantic-request.json').exists():continue
        request=strict_json_file(path=path/'semantic-request.json')
        if request.get('source_id')!=source['semantic_source_id']:continue
        requests.setdefault(request['request_id'],request)
    ordered=sorted(requests.values(),key=lambda r:source['required_unit_ids'].index(r['units'][0]['unit_id']))
    validate_request_partition(source,ordered)
    policy=calls._prepared_transport_policy(template)
    prepared=[replace(template,source_bytes=calls._source_json(source),
        request_bytes=calls._source_json(request),output_schema_bytes=calls._json(request['response_protocol']),
        provider_request_body_bytes=calls.request_body(request,policy,limits=template.limits),
        replay_only=True) for request in ordered]
    assessment=collect_native_assessments(prepared_requests=prepared,ledger=ledger,original_d04_inputs=True)
    require_complete_assessment(assessment)
    from .capacity_text_results import create_deterministic_text_candidate, build_text_evidence, build_text_review_unit, replay_text_result
    from .ordinary_source_authority import verify_ordinary_source_proofs
    from .sources import resolve_repository_file, raw_blob_record, source_reference_record
    from .specs import compile_spec_file
    from .traits import repository_company_traits
    from .review import _create_review_decision, _system_approved_claims, SYSTEM_REVIEWER_ID, SYSTEM_REVIEW_REASON
    from .d04_native_assessment import SPEC_PATH
    annual=source['prepared_annual_input'];period=annual['table_input']['target_period']
    spec=compile_spec_file(path=ROOT/SPEC_PATH,dependency_specs={})
    target={'company_id':company_id,'entity':annual['entity'],'accession':annual['filing']['accessionNumber'],
        'period_start':period['period_start'],'period_end':period['period_end'],
        'scope':spec['compiled']['required_claims'],'scope_key':content_hash(value=spec['compiled']['required_claims'])}
    records=[];references=[];raw={};represented=set()
    for d in source['documents']:
        ref,blob=d['source_reference'],d['raw_blob'];records.extend([blob,ref]);references.append(ref)
        raw[blob['raw_asset_id']]=resolve_repository_file(repo_root=source_root,repo_relative_path=blob['storage_uri']).read_bytes()
        represented.add((ref['source_url'],blob['raw_asset_id']))
    for proof in source['source_proofs']:
        if (proof['source_url'],'sha256:'+proof['content_sha256']) in represented:continue
        blob=raw_blob_record(repo_root=source_root,repo_relative_path=proof['request_repo_relative_path'],
            media_type='application/json' if proof['document_name'].endswith('.json') else 'text/plain')
        ref=source_reference_record(raw_blob=blob,company_id=company_id,source_url=proof['source_url'],
            accession=proof['accession'] or 'SUBMISSIONS-'+annual['entity'],document_name=proof['document_name'],
            source_role='supporting_input',request_attempt_id=proof['request_attempt_id'])
        records.extend([blob,ref]);references.append(ref)
    args={'compiled_spec':spec,'target':target,'source':source,'assessment':assessment,
        'source_references':[d['source_reference'] for d in source['documents']],'raw_bytes_by_id':raw}
    candidate=create_deterministic_text_candidate(**args)
    evidence=build_text_evidence(candidate=candidate,**args)
    unit,_=build_text_review_unit(compiled_spec=spec,candidate=candidate,evidence_check=evidence,
        source_bindings=args['source_references'])
    decision=_create_review_decision(review_unit=unit,decision='APPROVE',
        approved_claims=_system_approved_claims(review_unit=unit),required_claims=target['scope'],
        reviewer_type='SYSTEM',reviewer_id=SYSTEM_REVIEWER_ID,
        decided_at_utc=datetime.now(timezone.utc).isoformat(),reason=SYSTEM_REVIEW_REASON,supersedes_decision_id=None)
    result,trace,observations=replay_text_result(company_traits=repository_company_traits(repo_root=ROOT,company_id=company_id),
        candidate=candidate,evidence_check=evidence,review_unit=unit,review_decisions=[decision],**args)
    binding={'record_type':'CURRENT_SAVED_D04_COMPANY_INPUT','source_id':source['semantic_source_id'],
        'current_source_equivalence':equivalence,'source_proofs':current_source['source_proofs'],
        'assessment':assessment,'original_call_ordinals':[r['ordinal'] for r in assessment['completed']],
        'new_provider_execution':False,'production_authorized':False}
    return {'kind':'STRUCTURED','primary_metric_id':'D04','input_binding':binding,
        'compiled_specs':{'D04':spec},'spec_paths':{'D04':SPEC_PATH},'target_period':period,
        'prepared_annual_input':current_source['prepared_annual_input'],
        'references':references,'source_proofs':current_source['source_proofs'],
        'admission':verify_ordinary_source_proofs(data_root=source_root,proofs=current_source['source_proofs']),
        'expected_records':[*records,candidate,evidence,unit,decision,*observations,trace,result],
        'results':{'D04':result},'traces':{'D04':trace},
        'text_arguments':args,'registered_input':{'assessment':assessment},
        'selection':{'status':'TEXT_QUAL','assessment_mode':assessment['mode'],
                     'numeric_utilization_inferred':False},
        'source_assessment':assessment,'rules_root':str(ROOT)}

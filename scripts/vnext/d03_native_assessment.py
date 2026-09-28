"""D03 recorded per-request Candidate/Evidence, without company-result credit.

Only the explicit recorded controller may use this acceptor. A successful
source assessment still needs complete cross-group review, a D03 Result/Run
route, and separate live-call authority before it can answer the metric.
"""
from pathlib import Path

from .capacity_utilization_source import need
from .canonical import (content_hash, sha256_bytes, strict_json_file,
                        strict_json_loads)
from .normal_source_authority import ROOT

SPEC_PATH = 'catalog/r6/D03_regulatory_investigations_assessment_v1.md'
GROUP = 'd03_regulatory_source_assessment_v1'


def validate_response(*, request, source, raw_response):
    """Rebuild the old-fact successor from source before reading its answer."""
    from .continuous_semantic_calls import source_requests
    from .r6_regulatory_semantics import validate_response as base

    need(request.get('metric_id') == source.get('metric_id') == 'D03'
         and request['source_id'] == source['semantic_source_id'],
         'D03_NATIVE_SOURCE_OR_REQUEST_CHANGED')
    originals = source_requests(source)
    contract = request.get('source_fact_review_contract')
    if contract is not None:
        from .regulatory_fact_review import validate_candidate_response
        need(type(contract) is dict
             and type(contract.get('original_request_id')) is str,
             'D03_NATIVE_ANCHOR_CONTRACT_INVALID')
        matching = [original for original in originals
            if original['request_id'] == contract['original_request_id']
            and original['source_statement_facts']]
        need(len(matching) == 1, 'D03_NATIVE_ANCHOR_ORIGINAL_MISSING')
        checked = validate_candidate_response(original_request=matching[0],
            source=source, request=request, raw_response=raw_response,
            repo_root=ROOT)
        need(checked['source_fact_current_status_proven_by_program'] is False,
             'D03_NATIVE_OLD_SOURCE_FACT_CREDIT_RESTORED')
        return checked
    need(request in originals and not request['source_statement_facts'],
         'D03_NATIVE_UNSAFE_ORIGINAL_REQUEST')
    return base(request=request, raw_response=raw_response)


def build_acceptance(*, prepared, plan, response_body):
    """Attach one source-bound response to WB-3; never assert D03 as complete."""
    request = strict_json_loads(text=prepared.request_bytes.decode())
    source = strict_json_loads(text=prepared.source_bytes.decode())
    checked = validate_response(request=request, source=source,
                                raw_response=response_body)
    return _records(prepared=prepared, plan=plan, response_body=response_body,
                    checked=checked)


def _validate_bound_response(*, request, raw_response):
    """Response-only check after the controller authenticated this request."""
    need(request.get('record_type') == 'D03_INTERPRETATION_REQUEST'
         and request.get('metric_id') == 'D03'
         and not request.get('source_statement_facts'),
         'D03_BOUND_NATIVE_REQUEST_INVALID')
    if 'source_fact_review_contract' in request:
        from .regulatory_fact_review import _validate_bound_candidate_response
        need(type(request['source_fact_review_contract']) is dict
             and type(request.get('source_fact_candidates')) is list,
             'D03_BOUND_ANCHOR_CONTRACT_INVALID')
        return _validate_bound_candidate_response(
            request=request, raw_response=raw_response)
    from .r6_regulatory_semantics import validate_response as base
    return base(request=request, raw_response=raw_response)


def _build_bound_acceptance(*, prepared, plan, response_body):
    """Used only after build_plan authenticated source/request in this run."""
    request = strict_json_loads(text=prepared.request_bytes.decode())
    checked = _validate_bound_response(request=request,
                                       raw_response=response_body)
    return _records(prepared=prepared, plan=plan, response_body=response_body,
                    checked=checked)


def _records(*, prepared, plan, response_body, checked):
    from .capacity_native_assessment import _build_acceptance

    return _build_acceptance(prepared=prepared, plan=plan,
        response_body=response_body, checked=checked,
        metric_id='D03', group=GROUP, spec_path=SPEC_PATH,
        validator_path=Path(__file__))


def collect_recorded_assessments(*, company_id, ledger):
    """Read the exact complete current request set; grant no company result.

    This collection is a point-in-time view of an already initialized test
    ledger. It cannot use the real Issue #28 budget root or upgrade a recorded
    response into a provider execution.
    """
    from .continuous_call_policy import REQUIREMENT_ID
    from .continuous_semantic_calls import (
        _require_d03_recorded_ledger, prepare_d03_replay_only_requests)
    from .native_assessment_replay import replay_native_response
    from .capacity_native_assessment import d03_review_blockers
    from .native_request_construction import request_construction_session
    from .requirements import load_requirement_snapshot
    from .sources import resolve_repository_file

    _require_d03_recorded_ledger(ledger)
    need((ledger.root/'binding.json').is_file(),
         'D03_RECORDED_LEDGER_NOT_INITIALIZED')
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    with request_construction_session(requirement):
        prepared = prepare_d03_replay_only_requests(company_id=company_id)
        need(bool(prepared) and all(row.source_bytes == prepared[0].source_bytes
            and row.requirement['requirement_closure_hash'] ==
                requirement['requirement_closure_hash'] for row in prepared),
            'D03_RECORDED_COMPLETE_REQUEST_SET_CHANGED')
        source = strict_json_loads(text=prepared[0].source_bytes.decode())
        expected = [strict_json_loads(text=row.request_bytes.decode())
                    for row in prepared]
        by_id = {original['request_id']: (row, original)
                 for row, original in zip(prepared, expected)}
        need(len(by_id) == len(prepared)
             and [unit['unit_id'] for request in expected
                  for unit in request['units']] == source['required_unit_ids'],
             'D03_RECORDED_COMPLETE_SOURCE_PARTITION_CHANGED')
        with ledger.locked():
            state = ledger.snapshot()
        completed = {}
        failures = []
        seen = set()
        for claim in state['rows']:
            if claim['channel'] != 'PROVIDER':
                continue
            path = ledger.root/'calls'/('%04d' % claim['ordinal'])
            request_path = path/'semantic-request.json'
            if not request_path.exists():
                continue
            saved_bytes = resolve_repository_file(repo_root=path,
                repo_relative_path='semantic-request.json').read_bytes()
            saved = strict_json_loads(text=saved_bytes.decode())
            request_id = saved.get('request_id')
            if request_id not in by_id:
                continue
            selected, request = by_id[request_id]
            need(request_id not in seen
                 and saved_bytes == selected.request_bytes,
                 'D03_RECORDED_DUPLICATE_OR_CHANGED_REQUEST')
            seen.add(request_id)
            if claim['status'] != 'SUCCEEDED':
                failures.append({'request_id': request_id,
                    'ordinal': claim['ordinal'], 'status': claim['status']})
                continue
            replay = replay_native_response(prepared=selected, path=path)
            success = replay['success']
            accepted = success['acceptance_receipt']
            response_body = success['response_body']
            checked = _validate_bound_response(request=request,
                raw_response=response_body)
            blockers = d03_review_blockers(checked)
            need(accepted['candidate_record']['unresolved_competing_claims'] == blockers
                 and accepted['candidate_record']['selected'][
                     'source_assessment']['findings'] == checked['findings'],
                 'D03_RECORDED_REPLAYED_MEANING_CHANGED')
            terminal = strict_json_file(path=path/'terminal.json')
            completed[request_id] = {'request_id': request_id,
                'ordinal': claim['ordinal'],
                'terminal_id': terminal['terminal_id'],
                'acceptance_receipt_id': success['acceptance_receipt_id'],
                'response_sha256': sha256_bytes(content=response_body),
                'candidate': accepted['candidate_record'],
                'evidence': accepted['evidence_record'],
                'review_blockers': blockers,
                'candidate_reviews': checked.get('candidate_reviews', []),
                'source_revalidation': replay['revalidation']}
        missing = [request['request_id'] for request in expected
                   if request['request_id'] not in completed]
        rows = [completed[request['request_id']] for request in expected
                if request['request_id'] in completed]
        unresolved_request_ids = [row['request_id'] for row in rows
            if row['review_blockers']]
        proposed = [finding for row in rows for finding in row['candidate'][
            'selected']['source_assessment']['findings']
            if finding['kind'] == 'CURRENT_REGULATORY_ACTION'
            and finding['subject'] == 'TARGET_REGISTRANT'
            and finding['timing'] == 'CURRENT_REPORT']
        body = {'record_type': 'D03_RECORDED_NATIVE_ASSESSMENT_SET',
            'company_id': company_id, 'source_id': source['semantic_source_id'],
            'required_request_ids': [request['request_id'] for request in expected],
            'complete_source_unit_ids': source['required_unit_ids'],
            'completed': rows, 'missing_request_ids': missing,
            'failed_requests': failures,
            'unresolved_request_ids': unresolved_request_ids,
            'proposed_current_findings': proposed,
            'proposed_branch': ('INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE'
                if missing else 'UNRESOLVED_REQUIRES_NATIVE_REVIEW'
                if unresolved_request_ids else
                'COMPLETE_RECORDED_SET_REQUIRES_NATIVE_REVIEW'),
            'recorded_execution_revalidated': True,
            'semantic_correctness_verified': False,
            'native_review_complete': False,
            'native_result_or_run_created': False,
            'production_authorized': False}
        return {**body, 'assessment_set_id': content_hash(value=body)}

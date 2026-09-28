"""D03 recorded per-request Candidate/Evidence, without company-result credit.

Only the explicit recorded controller may use this acceptor. A successful
source assessment still needs complete cross-group review, a D03 Result/Run
route, and separate live-call authority before it can answer the metric.
"""
from pathlib import Path

from .capacity_utilization_source import need
from .canonical import strict_json_loads
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

"""Actual repository probes; synthetic source factories, never production evidence."""
from copy import deepcopy
import json
from types import SimpleNamespace

from tests.vnext.test_d04_native_assessment import request_for, response_for, text_arguments, D04NativeTextRecordsTest
from vnext.d04_native_assessment import validate_response, build_acceptance, requests_from_source
from vnext.r6_semantic_source import _bytes
from vnext.canonical import content_hash
from vnext.capacity_run import project_defined_absence

CASES = [
    ('There is substantial doubt about our ability to continue as a going concern, even if the proposed financing succeeds.', 'CONDITIONAL_OR_BOILERPLATE', 'CONDITIONAL'),
    ('There is substantial doubt about our ability to continue as a going concern; for example, cash is insufficient to meet obligations.', 'CONDITIONAL_OR_BOILERPLATE', 'CONDITIONAL'),
    ('In 2024 we incurred losses, and these conditions now raise substantial doubt about our ability to continue as a going concern.', 'HISTORICAL_STATEMENT', 'HISTORICAL'),
]

def observe(call):
    try:
        return {'accepted': True, 'value': call()}
    except ValueError as error:
        return {'accepted': False, 'error': str(error)}

def main():
    test = D04NativeTextRecordsTest()
    absent = test.reviewed_result(text_arguments('Revenue is recognized when services are delivered.', None, 'CURRENT_REPORT'))
    rows = []
    for text, wrong_kind, wrong_timing in CASES:
        row = {'statement': text, 'target_year': 2025, 'source_type': 'SYNTHETIC_LEGAL_FACTORY_INPUT'}
        for label, kind, timing in [('correct', 'DOUBT_DISCLOSED', 'CURRENT_REPORT'), ('incorrect', wrong_kind, wrong_timing)]:
            request = request_for(text, year=2025)
            response = response_for(request, kind, timing)
            def check():
                checked = validate_response(request=request, raw_response=_bytes(response))
                return {k: checked[k] for k in ('unresolved', 'current_target_findings')}
            result = {'validate_response': observe(check)}
            args = text_arguments(text, kind, timing)
            native_request = requests_from_source(args['source'])[0]
            finding = args['assessment']['source_findings'][0]
            native_response = response_for(native_request, kind, timing)
            native_response['units'][0]['findings'][0]['evidence'] = [{k:e[k] for k in ('kind', 'source_index')} for e in finding['resolved_evidence']]
            prepared = SimpleNamespace(request_bytes=_bytes(native_request), source_bytes=_bytes(args['source']))
            plan = {k:content_hash(value=k) for k in ('selected_representation_hash','ai_invocation_plan_id','source_identity_hash','task_contract_hash')}
            result['build_acceptance'] = observe(lambda: build_acceptance(prepared=prepared, plan=plan, response_body=_bytes(native_response))['evidence_status'])
            result['native_reviewed_result'] = observe(lambda: {k:v for k,v in test.reviewed_result(args).items() if k in ('value','value_kind','reason_code')})
            attack = deepcopy(args)
            attack['assessment']['proposed_branch'] = 'DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW'
            attack['assessment']['assessment_set_id'] = content_hash(value={k:v for k,v in attack['assessment'].items() if k != 'assessment_set_id'})
            result['public_absence_projection'] = observe(lambda: project_defined_absence(case={'registered_input':{'assessment':attack['assessment']}, 'selection':{'status':'TEXT_QUAL'},'text_arguments':attack}, result=absent, row={}, company={'display_name':'Sample','primary_cik':'12345'}))
            row[label] = result
        rows.append(row)
    print(json.dumps({'real_calls':[0,0,0], 'full_native_Run_executed':False, 'production_output_observed':False, 'cases':rows}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()

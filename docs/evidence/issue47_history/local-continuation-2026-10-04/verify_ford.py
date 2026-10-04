"""Bind source comparisons made by the executor; do not algorithmically judge them."""
import hashlib
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(REPO),str(REPO/'scripts')]
from tools.prepare_c02_table_context import assert_matches
from vnext.continuous_request_context import _load_tokenizer


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(inputs, output):
    if output.exists():
        raise FileExistsError('Retain previous checks')
    here=Path(__file__).parent
    answer_path=here/'ford-input-only/ford-development-answer.json'
    answer=json.loads(answer_path.read_bytes())
    request=inputs/'request-body.json'
    doc=json.loads((inputs/'document.json').read_bytes())
    grid=json.loads((inputs/'table-grid.json').read_bytes())
    view=json.loads(json.loads(request.read_bytes())['messages'][1]['content'])
    ref_path=REPO/'docs/evidence/issue47_history/c02-table-context-2026-10-04/reference-ford-2022.json'
    ref=json.loads(ref_path.read_bytes())
    freeze=json.loads((ref_path.parent/'ford-pre-trial-freeze.json').read_bytes())
    assert sha(ref_path)==freeze['files']['reference-ford-2022.json']
    assert sha(request)==ref['request_sha256']==freeze['request_sha256']
    assert sha(inputs/'document.json')==ref['document_artifact_sha256']
    assert sha(inputs/'table-grid.json')==ref['grid_artifact_sha256']
    raw=(inputs/'original-primary.bin').read_bytes()
    assert 'sha256:'+hashlib.sha256(raw).hexdigest()==doc['raw_asset_id']
    assert_matches(view,doc,grid)
    assert set(answer)=={'facts','unresolved'} and len(answer['facts'])==54 and len(answer['unresolved'])==3
    forward=[]
    kinds={'board_size','board_membership','board_independence','board_leadership',
           'committee_structure','committee_membership','committee_independence',
           'member_qualification','membership_change'}
    for i,fact in enumerate(answer['facts']):
        assert set(fact)=={'kind','statement','source_blocks','stated_time'} and fact['kind'] in kinds
        assert fact['source_blocks'] and len(set(fact['source_blocks']))==len(fact['source_blocks'])
        blocks=[]
        for n in fact['source_blocks']:
            assert type(n) is int and 0<=n<len(doc['blocks'])
            block=doc['blocks'][n]
            assert hashlib.sha256(raw[block['raw_start_byte']:block['raw_end_byte']]).hexdigest()==block['raw_span_sha256']
            blocks.append(block)
        forward.append({'independent_fact_index':i,'fact':fact,'original_blocks':blocks,
            'executor_source_read_disposition':'SUPPORTED_AS_STATED_BY_SOURCE',
            'c02_scope_disposition':'ISSUER_SKILL_DEMOGRAPHIC_AND_NOMINATION_ASSESSMENT_POLICY_PENDING' if i>=40 else 'SUPPORTED_COMPOSITION_OR_NAMED_STANDARD',
            'semantic_judgment_generated_by_checker':False})
    mapping=[ [1,0,36], [0,*range(3,17)], [18], [21], [19], [22],
        [3,24,27,28], [4,26,28], [5,39], [6,26,28], [7,26,28], [8,26,27,28],
        [9,28], [10,26,27,28], [11,25,26,27], [12,24,27], [13,25,27,28],
        [14,25,26,27], [15,24,27], [16,25,26,27,28], [24], [25], [26], [27],
        [28], [29,31,32], [33], [34,24], [30], [31], [20], [36], [35], [17], [] ]
    assert len(mapping)==len(ref['reference_units'])==35
    reverse=[{'original_reference':r,'independent_fact_indices':indices,
              'executor_comparison':'OMITTED_FROM_INDEPENDENT_ANSWER' if not indices else
                  'PRESENT_WITH_MORE_PRECISE_RECOMMENDATION_WORDING' if i==0 else 'SUPPORTED_RELATION_PRESENT'}
             for i,(r,indices) in enumerate(zip(ref['reference_units'],mapping))]
    tokenizer,fallback=_load_tokenizer();assert tokenizer is not None,fallback
    literal=answer_path.read_text();tokens=len(tokenizer.encode(literal,add_special_tokens=False).ids)
    compact=json.dumps(answer,ensure_ascii=False,separators=(',',':'))
    assert len(tokenizer.encode(compact,add_special_tokens=False).ids)==tokens
    report={'record_type':'ISSUE47_FORD_INPUT_ONLY_EXECUTOR_COMPARISON','request_sha256':sha(request),
        'pre_trial_reference_sha256':sha(ref_path),'answer_sha256':sha(answer_path),
        'model_to_original':forward,'original_to_model':reverse,'unresolved':answer['unresolved'],
        'independent_child_authorization':'One new read-only child explicitly approved in this local chat; fully consumed by this answer.',
        'independent_child_input':'Exact request only; no original reference, previous answer or repository conclusion.',
        'output_measurement':{'method':'PINNED_TOKENIZER_0.22.2_LITERAL_OUTPUT','tokens':tokens,
            'limit':4096,'fits':tokens<=4096,'provider_generation_with_cap_tested':False,
            'child_ui_approximation_is_not_this_measurement':True},
        'summary':{'source_supported_statements':54,'current_policy_supported_composition_statements':40,
            'policy_pending_issuer_assessment_statements':14,'reference_units_present':34,
            'reference_units_omitted':1,'omitted_reference_id':'F35','unresolved':3},
        'reference_wording_correction':{'reference_id':'F01','original_block':404,
            'finding':'The frozen reference says the size was reduced; the original says the Committee recommended reducing it. Preserve the frozen reference and retain this qualification; the independent answer is more literal here.'},
        'counterchecks':{'lynn_audit_eligibility_not_membership':True,'huntsman_executive_role_not_board_departure':True,
            'current_in_filing_not_2022_year_end_snapshot':True,'uninterpreted_images_remain_unresolved':True},
        'development_method_status':'NOT_READY_FOR_TARGET_MODEL_VALIDATION',
        'reasons':['F35 Edsel B. Ford II former-director fact omitted despite supplied B1013/B1015.',
                   'Literal complete answer exceeds 4096 output tokens; whitespace compaction does not fix it.',
                   'Issuer assessments remain policy-pending and images are not interpreted.'],
        'no_answer_trim_or_rescue':True,'new_runs':0,'new_acceptances':0,'calls':[0,0,0],
        'production_authorized':False}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'facts':54,'reference_units_present':34,'omitted':'F35','output_tokens':tokens,'fits':tokens<=4096,'new_acceptances':0}))


if __name__=='__main__':
    verify(Path(sys.argv[1]),Path(sys.argv[2]))

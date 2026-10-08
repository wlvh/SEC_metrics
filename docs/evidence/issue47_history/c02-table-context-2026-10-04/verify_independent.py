"""Check source identities, locators and literal output size, not semantics.

The executor separately read the 46 statements, their 113 cited blocks and
the original membership grid. The reverse reference covers seven relations,
not a complete inventory of every composition fact in the original filing.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]
from tools.prepare_c02_table_context import assert_matches
from vnext.continuous_request_context import _load_tokenizer


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(inputs, original_inputs, out):
    answer_path = HERE / 'independent-input/independent-result.json'
    answer = json.loads(answer_path.read_bytes())
    compact = HERE / 'independent-input/compact-response.json'
    assert json.loads(compact.read_bytes()) == answer
    request = inputs / 'request-body.json'
    view = json.loads(json.loads(request.read_bytes())['messages'][1]['content'])
    original = json.loads((original_inputs / 'document.json').read_bytes())
    grid = json.loads((original_inputs / 'table-grid.json').read_bytes())
    assert_matches(view, original, grid)
    metadata = json.loads((HERE / 'jpmorgan_chase-2021-12-31-input.json').read_bytes())
    assert sha(request) == metadata['artifacts']['request-body.json']
    assert sha(original_inputs / 'document.json') == metadata['artifacts']['document.json']
    assert sha(original_inputs / 'table-grid.json') == metadata['artifacts']['table-grid.json']
    kinds = {'board_size', 'board_membership', 'board_independence', 'board_leadership',
             'committee_structure', 'committee_membership', 'committee_independence',
             'member_qualification', 'membership_change'}
    assert set(answer) == {'facts', 'unresolved'} and len(answer['facts']) == 46 <= 64
    forward = []
    for i, f in enumerate(answer['facts']):
        assert set(f) == {'kind', 'statement', 'source_blocks', 'stated_time'}
        assert f['kind'] in kinds and f['source_blocks']
        assert all(type(n) is int and 0 <= n < view['block_count'] for n in f['source_blocks'])
        forward.append({'fact_index': i, 'fact': f,
                        'source_blocks': [original['blocks'][n] for n in f['source_blocks']],
                        'executor_disposition': 'SUPPORTED_AS_THE_FILINGS_STATED_ASSESSMENT_OR_COMPOSITION',
                        'qualification_policy_resolution_claimed': False})
    for f in answer['unresolved']:
        assert set(f) == {'source_blocks', 'reason'} and f['source_blocks']
        assert all(type(n) is int and 0 <= n < view['block_count'] for n in f['source_blocks'])
    reference_path = HERE / 'reference-jpmorgan-2021.json'
    reference = json.loads(reference_path.read_bytes())
    reverse = []
    # The manually compared two independent statements are facts 24 and 25.
    for r in reference['membership_relations']:
        fact_index = 24 if r['committee_code'] == 'A' else 25
        f = answer['facts'][fact_index]
        assert r['name_as_printed'].removesuffix('2') in f['statement']
        assert r['committee_name_from_legend'].removesuffix(' Committee') in f['statement']
        assert 'CURRENT_IN_FILING' in f['stated_time'] and '2021' in f['stated_time']
        reverse.append({'original_relation': r, 'independent_fact_index': fact_index,
                        'executor_comparison': 'MATCH_MEMBERSHIP_AND_SEPARATE_TEMPORAL_SCOPES'})
    tokenizer, fallback = _load_tokenizer(); assert tokenizer is not None, fallback
    report = {'record_type': 'ISSUE_47_C02_INDEPENDENT_INPUT_BOUND_RELATION_TRIAL',
              'authorization': 'User explicitly allowed one read-only child agent in this conversation. No model-provider/SEC/paid-budget permission was added.',
              'reader_scope': 'Independent child received only the exact request-body system/user input, not the original reference, source HTML, old answers or repository instructions. Main executor then performed source comparison.',
              'request_sha256': sha(request), 'original_reference_sha256': sha(reference_path),
              'independent_answer_sha256': sha(answer_path), 'compact_answer_sha256': sha(compact),
              'reading_log_sha256': sha(HERE / 'independent-input/reading-log.json'),
              'model_to_original': forward, 'original_to_model': reverse,
              'unresolved': answer['unresolved'],
              'output_measurement': {'reference_tokenizer_only': True,
                                     'archive_tokens': len(tokenizer.encode(answer_path.read_text()).ids),
                                     'literal_compact_json_tokens': len(tokenizer.encode(compact.read_text()).ids),
                                     'output_limit': 4096, 'archive_format_fits': False,
                                     'literal_compact_json_fits': len(tokenizer.encode(compact.read_text()).ids) <= 4096,
                                     'objects_identical': True, 'provider_usage': None,
                                     'provider_generation_with_output_cap_tested': False},
              'complete_original_fact_inventory_prepared_before_trial': False,
              'reverse_scope': 'All seven original A/B membership relations only; forward reading covers all 46 emitted facts. Independent full supplied input coverage does not enlarge the pre-trial original reference.',
              'limitations': ['Uninterpreted images and exact 2021-12-31 membership remain unresolved.',
                              'Qualification and role-evaluation policy question to Issue #28 remains open.',
                              'This reused development source is not a new holdout.',
                              'Original pretty JSON exceeds 4096; literal whitespace compaction fits without changing facts, but is not proof a provider produces complete output within its cap.'],
              'new_acceptance_entries': 0, 'new_native_runs': 0,
              'calls': [0, 0, 0], 'production_authorized': False}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'facts': 46, 'unresolved': 4, 'reverse_relations': len(reverse),
                      'archive_tokens': report['output_measurement']['archive_tokens'],
                      'compact_tokens': report['output_measurement']['literal_compact_json_tokens'],
                      'new_acceptance': 0}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--original-inputs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); main(a.inputs, a.original_inputs, a.out)

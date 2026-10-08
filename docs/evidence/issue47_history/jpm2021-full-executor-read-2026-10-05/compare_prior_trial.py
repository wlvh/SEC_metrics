"""Record manual comparison to the unchanged earlier independent trial.

The correspondence below is the executor's semantic judgment after complete
text and necessary table reading. Mechanical checks only verify identities,
literal source indices, token counts and that neither original object changed.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compare(inputs, reference_path, frozen_path, answer_path, code_root):
    sys.path.insert(0, str(code_root / 'scripts'))
    from vnext.continuous_request_context import _load_tokenizer
    raw = answer_path.read_bytes()
    assert sha(raw) == 'ed9e7dc14d87fd86c8b12da0ebf7e7871fd131a9234fb13313dffef13b1e8d8e'
    reference_raw = reference_path.read_bytes()
    frozen = json.loads(frozen_path.read_bytes())
    assert frozen['reference_sha256'] == sha(reference_raw)
    assert frozen['pre_original_trial_claimed'] is False
    ref = json.loads(reference_raw)
    answer = json.loads(raw)
    assert len(answer['facts']) == 46 and len(answer['unresolved']) == 4
    doc = json.loads((inputs / 'document.json').read_bytes())
    source = (inputs / 'original-primary.bin').read_bytes()
    cited = set()
    for entry in answer['facts'] + answer['unresolved']:
        for index in entry['source_blocks']:
            assert type(index) is int and 0 <= index < len(doc['blocks'])
            block = doc['blocks'][index]
            assert sha(source[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256']
            cited.add(index)
    # One-based answer fact ordinals. Unit counts differ because boundary and
    # policy annotations are not output facts; no 49-versus46 subtraction.
    mapping = {
        1: [], 2: [1, 13], 3: [2], 14: [15], 15: [7, 16], 16: [17],
        17: [18], 23: [19], 24: [19], 25: [25], 26: [26], 27: [30],
        28: [43, 44], 29: [28, 31, 43], 30: [27], 31: [46],
        32: [14], 33: [], 44: [32], 45: [45], 46: [], 47: [29], 48: [], 49: [],
    }
    mapping.update({r: [r - 1] for r in range(4, 14)})
    mapping.update({r: [r + 2] for r in range(18, 23)})
    mapping.update({r: [r - 1] for r in range(34, 44)})
    assert set(mapping) == set(range(1, 50))
    correspondence = []
    for unit in ref['reference_units']:
        number = int(unit['id'][1:])
        correspondence.append({'reference_unit': unit['id'],
                               'prior_answer_fact_ordinals': mapping[number]})
    tokenizer, fallback = _load_tokenizer()
    assert tokenizer is not None, fallback
    compact = json.dumps(answer, ensure_ascii=False, separators=(',', ':'))
    assert answer_path.read_bytes() == raw and reference_path.read_bytes() == reference_raw
    return {
        'record_type': 'ISSUE47_JPM2021_POST_TRIAL_FULL_SOURCE_COMPARISON',
        'compared_at': datetime.now(timezone.utc).isoformat(),
        'reference_sha256': sha(reference_raw), 'prior_answer_sha256': sha(raw),
        'prior_answer_facts': 46, 'prior_answer_unresolved': 4,
        'forward_source_supported_fact_ordinals': list(range(1, 47)),
        'forward_manual_reading_not_a_programmatic_semantic_verdict': True,
        'citation_occurrences_in_facts': sum(len(x['source_blocks']) for x in answer['facts']),
        'distinct_cited_blocks_in_facts_and_unresolved': len(cited),
        'reverse_reference_correspondence': correspondence,
        'all_16_principal_positive_relations_present': True,
        'all_7_specific_A_B_positive_relations_present': True,
        'manual_findings': [
            'Names, tenures, nine independence determinations, parent leadership, '
            'five principal committees, Stock/Executive, two specific bodies, '
            'all23positive members and dated reports are already represented. '
            'Do not count these as new omissions.',
            'Bammann former-officer/joining relation is present in fact46. '
            'The separate no-other-CMDC-member-was-ever-an-officer/employee '
            'clause1387/1388 is not explicit; its C02qualification/role scope '
            'remains an owner question, not a confirmed core omission.',
            'Actual75percent-or-more meeting attendance is not represented; '
            '2021annualmeeting attendance in fact2 is a different fact. '
            'The broader performance/role scope remains pending.',
            'Eleven issuer attributes/biography assessments are attributed, '
            'not independent credential checks. Their policy scope is pending.',
            'Fact29 quotes the broad later committee-independence claim as a '
            'filing statement; it does not name unknownStock/Executivemembers. '
            'Keep this attribution and the source-scope uncertainty.',
            'Parent election2021 is present. SubsidiaryBank/IHCboards, heritage '
            'company roles, conditionalfutureChairpolicy, ownership21person '
            'group and management succession are separate boundaries, not '
            'automatic missing parentcomposition facts.',
            'All four original uncertainties remain genuine: additional '
            'committee members/chairs, specificchair/timeframe, uninterpreted '
            'matrixmarks, and lack of an exactDecember31snapshot.'
        ],
        'saved_pretty_artifact_tokens': len(tokenizer.encode(raw.decode(), add_special_tokens=False).ids),
        'lossless_compact_object_tokens': len(tokenizer.encode(compact, add_special_tokens=False).ids),
        'compact_string_saved_or_reemitted_as_answer': False,
        'literal_original_returned_message_or_provider_usage_proven': False,
        'compact_size_only_proves_representability_not_fresh_generation': True,
        'reference_created_before_original_independent_trial': False,
        'other_426_tables_or_images_completely_reviewed': False,
        'original_answers_or_references_changed': False,
        'normal_runtime_or_reading_view_updated': False,
        'new_native_run_or_full_metric_acceptance': False,
        'calls': [0, 0, 0], 'new_runs': 0, 'new_acceptances': 0,
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--frozen', type=Path, required=True)
    p.add_argument('--answer', type=Path, required=True)
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    value = compare(args.inputs, args.reference, args.frozen, args.answer, args.code_root)
    with args.out.open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: value[k] for k in ['prior_answer_facts', 'prior_answer_unresolved',
                      'all_16_principal_positive_relations_present', 'all_7_specific_A_B_positive_relations_present',
                      'saved_pretty_artifact_tokens', 'lossless_compact_object_tokens', 'calls']}, indent=1))

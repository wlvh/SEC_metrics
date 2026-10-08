"""Record manual findings, using code only to bind original excerpt bytes."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--records', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.document.read_text())
    blocks = {b['block_index']: b for b in document['blocks']}
    rows = [json.loads(line) for line in args.records.read_text().splitlines()]
    observations = [r for r in rows if r['record_type'] == 'VERIFIED_OBSERVATION']
    result = next(r for r in rows if r['record_type'] == 'METRIC_RESULT')
    checked = []
    for observation in observations:
        binding = observation['source_binding']['text_binding']
        assert binding['document_id'] == document['text_document_id']
        block = blocks[binding['block_index']]
        assert observation['value'] == block['text']
        assert all(binding[k] == block[k] for k in
                   ('raw_start_byte', 'raw_end_byte', 'raw_span_sha256'))
        checked.append({'order': binding['order'], 'block_index': block['block_index'],
                        'text': block['text'], 'observation_id': observation['observation_id']})
    selected = {r['block_index'] for r in checked}
    assert len(checked) == 58
    findings = []

    def add(kind, statement, indexes):
        findings.append({'kind':kind, 'manual_judgment':statement,
                         'source_blocks':[dict(blocks[i], selected=i in selected) for i in indexes]})

    add('MISSING_IDENTITY_RELATION',
        'Two identical Chairman/CEO title excerpts have no selected adjacent James Dimon name. The complete input explicitly names him; a reader cannot recover that ownership just from the isolated title or assume it belongs to the preceding director.',
        [380,383,750,751,766,767])
    add('MISSING_COMMITTEE_NAMES',
        'The saved selection states two additional standing committees but omits the explicitly named Stock Committee and Executive Committee.',
        [1243,1244,1245])
    add('MISSING_SPECIFIC_PURPOSE_RELATIONS',
        'The current two committee names, the 2025 A/B legend and all four positive named A/B relations are absent. Full table cells in the separate executor reference support the positives; unexamined image cells remain unresolved.',
        [1249,1252,1256,1258,1259,1261,1266,1268,1270,1272,1279,1280,1281])
    add('MISSING_NAMED_STANDARD',
        'Bammann is selected as Risk Chair, but the separately stated Federal Reserve standard for risk experience is absent. This does not convert experience into membership; membership is supported separately by the roster/card.',
        [660,1173])
    add('OUTSIDE_COMPOSITION_FACTS',
        'The director share-retention/anti-hedging policy block is a governance procedure; it does not identify a director, committee member, chair or a specific qualification determination.',
        [1504])
    add('POLICY_PENDING',
        'The all-nominee personal attributes/assessment block remains pending the #28 qualification/role interpretation; no acceptance is inferred from its source support.',
        [541])
    add('MIXED_BLOCKS_REQUIRE_MEANING',
        'These blocks contain actual committee or leadership facts together with rationale/process. Their true facts remain source-supported; classifying each entire block simply as false would lose the actual determinations.',
        [54,1087,1089,3548])
    add('TIME_NOT_INFERRED',
        'The proxy explicitly separates current incumbents, a proposed one-year 2026 election term, historical 2025 meeting attendance, and the December 2025 Combs resignation. Annual FY2025 grouping is not a December31 snapshot.',
        [527,528,529,530,1003,1502])
    add('NAMED_AUDIT_QUALIFICATION_ALREADY_SUPPORTED',
        'The saved Audit report paragraph plus its four signed names supports the named independence/financial-literacy/SEC financial-expert relations. Do not count the omitted duplicate B1173 Audit statement as four new missing qualifications.',
        [1173,3409,3440,3441,3442,3443,3444])
    body = {'record_type':'ISSUE47_MANUAL_SAVED_C02_SELECTION_COMPARISON',
            'position':'jpmorgan_chase:2025-12-31',
            'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest(),
            'old_records_sha256':hashlib.sha256(args.records.read_bytes()).hexdigest(),
            'result_id':result['result_id'],
            'candidate_hash':result['text_payload']['candidate_hash'],
            'all_58_selected_excerpt_bindings_equal_original':True,
            'selected_excerpts':checked, 'manual_findings':findings,
            'scope':'The entire supplied proxy text and two necessary member tables have been read. This comparison records specified semantic findings rather than claiming a complete all-media/qualification-policy error census.',
            'judgment':'FULL_METRIC_ACCEPTANCE_WITHHELD',
            'old_records_modified':False, 'selector_repaired':False,
            'new_runs':0, 'new_acceptances':0, 'calls':[0,0,0]}
    args.out.write_text(json.dumps(body,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'checked_excerpts':58,'manual_findings':len(findings),
                      'all_media_acceptance':False,'calls':[0,0,0]}))


if __name__ == '__main__':
    main()

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
    assert len(checked) == 62
    findings = []

    def add(kind, statement, indexes):
        findings.append({'kind':kind, 'manual_judgment':statement,
                         'source_blocks':[dict(blocks[i], selected=i in selected) for i in indexes]})

    add('MISSING_IDENTITY_RELATION',
        'Two isolated Chairman/CEO title excerpts omit the adjacent James Dimon names. The input explicitly names the title owner. Other mentions of Mr. Dimon do not restore the omitted full-name/card relationship.',
        [368,371,771,772])
    add('MISSING_COMMITTEE_NAMES',
        'The saved selection counts two additional standing committees but omits Stock Committee and Executive Committee names.',
        [1231,1232,1233])
    add('MISSING_SPECIFIC_PURPOSE_RELATIONS',
        'The current Markets Compliance/Omnibus names and five positive A/B relations/legend are absent. The reference preserves the current heading and explicit2024 legend together; blank image cells are unresolved.',
        [1236,1239,1243,1245,1246,1248,1250,1252,1256,1258,1260,1261,1268,1269,1270])
    add('MISSING_NAMED_STANDARD',
        'The Federal Reserve risk-experience determination for Risk Chair Bammann is absent; membership is separately supported by her selected card. Audit qualification is not counted missing merely because its duplicate clause in this block is omitted.',
        [643,1161])
    add('MISSING_STANDARD_ATTRIBUTION',
        'General all-nominee independence is selected, and Burke has specific NYSE/Firm attribution in the issuer response. The explicit current eleven and retired Flynn/Neal NYSE/Firm determinations are omitted. This is narrower than claiming that all independence facts are missing.',
        [335,996,1003,1004,3489])
    add('OUTSIDE_COMPOSITION_FACTS',
        'The director share-retention/anti-hedging paragraph describes a policy, not a current named composition or qualification determination.',
        [1494])
    add('CONDITIONAL_POLICY',
        'The historical half-of-six transitions/considering next transition paragraph is a policy/history statement, not an actual upcoming appointment. Preserve current maintained structure separately.',
        [1076,1078,1079,3475])
    add('POLICY_PENDING',
        'The nominee personal-attributes assessment remains pending #28 qualification meaning; source support alone supplies no acceptance.',
        [525])
    add('EFFECTIVE_DATES_AND_RETIREMENT_ALREADY_SUPPORTED',
        'B1040 and B1272 already preserve the two election decisions and distinct2025 effective dates. Flynn/Neal retirement blocks are also selected. Do not count these facts missing just because another duplicate current status/roster block was omitted.',
        [1040,1272,1491,1492])
    add('NAMED_AUDIT_QUALIFICATION_ALREADY_SUPPORTED',
        'The Audit paragraph and signed four names support the named NYSE/SEC independence, financial literacy and SEC financial-expert relations. The date of the report remains explicitly available in the reference.',
        [3386,3416,3417,3418,3419,3420,3421])
    body = {'record_type':'ISSUE47_MANUAL_SAVED_C02_SELECTION_COMPARISON',
            'position':'jpmorgan_chase:2024-12-31',
            'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest(),
            'old_records_sha256':hashlib.sha256(args.records.read_bytes()).hexdigest(),
            'result_id':result['result_id'],
            'candidate_hash':result['text_payload']['candidate_hash'],
            'all_62_selected_excerpt_bindings_equal_original':True,
            'selected_excerpts':checked, 'manual_findings':findings,
            'scope':'The entire supplied proxy text and two necessary member tables have been read. This comparison records specified semantic findings rather than claiming a complete all-media/qualification-policy error census.',
            'judgment':'FULL_METRIC_ACCEPTANCE_WITHHELD',
            'old_records_modified':False, 'selector_repaired':False,
            'new_runs':0, 'new_acceptances':0, 'calls':[0,0,0]}
    args.out.write_text(json.dumps(body,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'checked_excerpts':62,'manual_findings':len(findings),
                      'all_media_acceptance':False,'calls':[0,0,0]}))


if __name__ == '__main__':
    main()

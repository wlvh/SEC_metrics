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
        'The James Dimon card title is selected without its adjacent full name. Other partial Mr.Dimon mentions do not repair the card ownership.', [388,391,747,748])
    add('MISSING_COMMITTEE_NAMES',
        'The additional-standing-committee count is selected, but Stock and Executive names are absent.', [1189,1190,1191])
    add('MISSING_SPECIFIC_PURPOSE_RELATIONS',
        'Markets Compliance/Omnibus names and the six positive A/B relations with their2023 legend are absent. The complete current table in the reference is text, not guessed from blank image cells.',
        [1194,1195,1207,1211,1212,1213,1214,1222,1224,1225,1226,1229,1232,1233,1234])
    add('MISSING_CURRENT_PRC_MEMBERSHIP',
        'Neal Audit membership is supported by the selected signed report, but his separate current PRC membership is only in the unselected member matrix.', [1225,1226,3649])
    add('MISSING_NAMED_STANDARD',
        'Bammann Risk Chair is selected; the Federal Reserve risk-experience determination is absent.', [649,1129])
    add('MISSING_STANDARD_ATTRIBUTION',
        'General nominee independence and Audit/CMDC additional criteria are selected. The named eleven NYSE/Firm-independent nonmanagement directors, including two non-nominee current directors, are absent; this does not mean all independence statements are missing.', [352,960,966,967,3720])
    add('QUALIFICATION_AND_PROSPECTIVE_CHANGES_ALREADY_SUPPORTED',
        'Gorsky SEC financial-expert determination in anticipation of Audit service is already selected. So are conditional future Audit/PRC membership, Risk conclusion, and Weinberger future Audit Chair. Preserve qualification independently from current membership; do not count these present source statements missing.', [423,1130,1237,1239])
    add('AUDIT_AND_CURRENT_RETIREMENT_STATUS_ALREADY_SUPPORTED',
        'The current Audit report/signed names supports Flynn Chair, Neal/Novakovic/Weinberger membership and named qualifications. Selected retirement footnotes are future term expiry, not completed retirement at proxy date.', [1236,1238,3614,3646,3647,3648,3649,3650,3651])
    add('POLICY_AND_MIXED_BLOCKS',
        'B3729 is general Board judgment/process, while B3734 concerns a conditional future leadership policy. B3730/B3733 also contain real current combined-role determinations together with rationale; those real facts are not reclassified false.', [3729,3730,3733,3734])
    add('COUNT_FRAME_UNRESOLVED',
        'Current twelve-name committee table, ten nominees, eleven named independent nonmanagement directors, and nine nonemployee Directors in a proposedPlan participation paragraph are distinct frames. The Plan may anticipate post-retirement nominees, but source correspondence is not proved and no number is silently replaced.', [352,533,534,966,1207,3378])
    body = {'record_type':'ISSUE47_MANUAL_SAVED_C02_SELECTION_COMPARISON',
            'position':'jpmorgan_chase:2023-12-31',
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

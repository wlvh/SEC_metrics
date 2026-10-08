"""Record manual semantic findings; code checks exact excerpt bindings only."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    for name in ('document', 'records', 'reference', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.document.read_text())
    blocks = {b['block_index']:b for b in document['blocks']}
    records = [json.loads(line) for line in args.records.read_text().splitlines()]
    result = next(r for r in records if r['record_type']=='METRIC_RESULT')
    checked = []
    for r in records:
        if r['record_type'] != 'VERIFIED_OBSERVATION':
            continue
        binding = r['source_binding']['text_binding']
        assert binding['document_id'] == document['text_document_id']
        b = blocks[binding['block_index']]
        assert r['value'] == b['text']
        assert all(binding[k] == b[k] for k in ('raw_start_byte','raw_end_byte','raw_span_sha256'))
        checked.append({'order':binding['order'],'block_index':b['block_index'],
                        'text':b['text'],'observation_id':r['observation_id']})
    assert len(checked) == 57
    selected = {r['block_index'] for r in checked}
    findings = []

    def add(kind, statement, indexes):
        findings.append({'kind':kind,'manual_judgment':statement,
                         'source_blocks':[dict(blocks[i], selected=i in selected) for i in indexes]})

    add('MISSING_IDENTITY_RELATION',
        'James Dimon card title806 is selected without adjacent full name805; the role should remain attached to its named person, not inferred from company or partial surname.',[804,805,806,810])
    add('MISSING_COMMITTEE_NAMES',
        'The additional standing committee count1244 is selected, while Stock and Executive committee names1245/1246 are absent.',[1244,1245,1246])
    add('MISSING_SPECIFIC_PURPOSE_RELATIONS',
        'Markets Compliance/Omnibus names and all seven positive A/B relations are absent. Preserve both current membership heading and explicit2022 legend; do not resolve that time distinction silently.',
        [1249,1250,1262,1266,1267,1268,1269,1270,1275,1276,1278,1279,1280,1281])
    add('MISSING_EXPLICIT_ASSIGNMENT_STATE',
        'Davis Board appointment is already selected1052/1283. Her explicit Committees: Not yet assigned780 is absent; blank cells alone are weaker than the actual statement.',[779,780,781,1052,1283])
    add('MISSING_NAMED_STANDARD',
        'Audit signed report3504 already supports SEC expert, financial literacy and independence for its three named members. The separate explicit2022 SEC-and-NYSE financial-expert definition, and Federal Reserve risk-experience determination for Bammann, are absent1185.',[1185,3504,3537,3538,3539,3540])
    add('MISSING_STANDARD_ATTRIBUTION',
        'All nominees independent except CEO380 and Audit/CMDC additional criteria1021 are selected. The named eleven nonmanagement directors under general NYSE/Firm standards1020 are absent. This is narrower than saying all independence evidence is missing.',[380,1020,1021,3599])
    add('EXPLICIT_TENURE_FIELDS_ABSENT',
        'Individual Director since fields in the cards are absent. Selected1052/1283 already supplies GorskyJuly2022 and DavisMarch2023 effective appointments; do not count those supported years absent. The reference retains the other named tenure fields and Dimon Chair2006/CEO2005 separately from predecessor BankOne.',
        [441,666,691,723,746,779,804,810,835,860,900,924,951,977,1052,1283])
    add('CURRENT_AUDIT_AND_APPOINTMENTS_ALREADY_SUPPORTED',
        'Selected current Audit report and signed FlynnChair/Neal/Novakovic names are sufficient for those membership/qualifications. Selected appointment months are distinct; FY2022 annual container is not a twelve-member year-end snapshot. Hobson is PRC member, Crown current PRC Chair.',[585,748,902,1052,1283,3504,3538,3539,3540])
    add('POLICY_AND_MIXED_BLOCKS',
        '3608 is general discretion/rationale;1104/3613 are conditional nextCEO policies rather than completed chair appointments.1100/1103/3611 also contain real current combinedChairCEO/BurkeLeadIndependent determinations; preserve those real facts.589 is issuer nominee assessment pending qualification-policy interpretation, not established regulatory qualification.',[589,1100,1103,1104,3608,3611,3613])
    body = {'record_type':'ISSUE47_MANUAL_SAVED_C02_SELECTION_COMPARISON',
            'position':'jpmorgan_chase:2022-12-31',
            'reference_sha256':hashlib.sha256(args.reference.read_bytes()).hexdigest(),
            'old_records_sha256':hashlib.sha256(args.records.read_bytes()).hexdigest(),
            'result_id':result['result_id'],'candidate_hash':result['text_payload']['candidate_hash'],
            'all_57_selected_excerpt_bindings_equal_original':True,
            'selected_excerpts':checked,'manual_findings':findings,
            'scope':'Entire supplied proxy text and two necessary member tables read. Specified findings are not a complete all-media/qualification-policy error census.',
            'judgment':'FULL_METRIC_ACCEPTANCE_WITHHELD','old_records_modified':False,
            'selector_repaired':False,'new_runs':0,'new_acceptances':0,'calls':[0,0,0]}
    args.out.write_text(json.dumps(body,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'checked_excerpts':57,'manual_findings':len(findings),'calls':[0,0,0]}))


if __name__ == '__main__':
    main()

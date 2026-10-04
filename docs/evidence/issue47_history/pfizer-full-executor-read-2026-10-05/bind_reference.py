"""Bind executor-read Pfizer statements to the unchanged supplied input.

Code verifies bytes and locators, not business meaning or accepted coverage.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    for name in ('input','reading-notes','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    doc=json.loads((args.input/'document.json').read_text())
    grid=json.loads((args.input/'table-grid.json').read_text())
    metadata=json.loads((args.input/'metadata.json').read_text())
    notes=json.loads(args.reading_notes.read_text())
    raw=(args.input/'original-primary.bin').read_bytes()
    assert sha(raw)==doc['raw_asset_id'][7:]
    blocks={b['block_index']:b for b in doc['blocks']}
    assert set(blocks)==set(range(3511))
    assert notes['complete_supplied_visible_text_read'] is True
    assert [i for p in notes['read_packets'] for i in range(p['blocks'][0],p['blocks'][1]+1)]==list(range(3511))
    for b in blocks.values():assert sha(raw[b['raw_start_byte']:b['raw_end_byte']])==b['raw_span_sha256']
    for name,digest in metadata['artifacts'].items():assert sha((args.input/name).read_bytes())==digest
    table=next(t for t in grid['tables'] if t['table_id']=='table_000032')
    units=[]

    def add(statement,indexes,kind,scope,cells=()):
        locators=[]
        for row,column in cells:
            cell=table['rows'][row]['cells'][column]
            assert (cell['row_index'],cell['column_index'])==(row,column)
            locators.append({'table_id':table['table_id'],**cell})
        units.append({'reference_unit_id':f'P22-{len(units)+1:02}',
                      'kind':kind,'statement':statement,'time_scope':scope,
                      'source_blocks':[blocks[i] for i in indexes],
                      'table_cells':locators,'authority':'EXECUTOR_MANUAL_DEVELOPMENT_REFERENCE'})
    for note in notes['reference_notes']:
        add(note['statement'],note['blocks'],'CONSOLIDATED_READ_NOTE',
            'The statement preserves its actual source time, speaker and entity.')
    current='Proxy March16,2023; FY2022 is an annual container. The December31 date46 applies to the milestone summary, not automatically the whole Board disclosure.'
    roster=[
        ('Ronald E. Blaylock',2017,'Audit and Compensation member',4,[475,485,486,487]),
        ('Albert Bourla',2018,'Chair sinceJanuary2020 and CEO sinceJanuary2019; no principal committee named in summary',5,[198,199,493,500,504]),
        ('Susan Desmond-Hellmann',2020,'Governance & Sustainability and Science and Technology member',6,[515,526,527,528]),
        ('Joseph J. Echevarria',2015,'Audit member and Governance & Sustainability Chair',7,[536,549,550]),
        ('Scott Gottlieb',2019,'Regulatory and Compliance Chair and Science and Technology member',8,[561,569,570,571]),
        ('Helen H. Hobbs',2011,'Governance & Sustainability/Regulatory and Compliance member and Science and Technology Chair',9,[577,584,585,586]),
        ('Susan Hockfield',2020,'Regulatory and Compliance and Science and Technology member',10,[595,606,607,608]),
        ('Dan R. Littman',2018,'Governance & Sustainability/Regulatory and Compliance/Science and Technology member',11,[615,622,623,624]),
        ('Shantanu Narayen',2013,'Lead Independent Director since2018, re-elected in the late2022 annual review; no principal committee named in summary',12,[223,224,633,643,644,724,3136,3140]),
        ('Suzanne Nora Johnson',2007,'Audit Chair and Regulatory and Compliance member',13,[653,665,666,667]),
        ('James Quincey',2020,'Compensation member',14,[678,687,688,689]),
        ('James C. Smith',2014,'Audit member and Compensation Chair',15,[697,704,705]),
    ]
    for name,since,role,row,indexes in roster:
        add(f'{name} is one of twelve current directors standing for re-election; director since{since}; {role}.',
            [355]+indexes,'NAMED_CURRENT_COMPOSITION',current,[(row,0),(row,9)])
    add('All eleven current non-Bourla directors are determined independent under Pfizer Standards, which meet and in some respects exceed NYSE independence requirements. The actual named set is Blaylock, Desmond-Hellmann, Echevarria, Gottlieb, Hobbs, Hockfield, Littman, Narayen, Nora Johnson, Quincey and Smith.',
        [401,409,410,411,726,3123],'NAMED_INDEPENDENCE_STANDARD',current)
    add('Audit Chair Nora Johnson and members Blaylock/Echevarria/Smith are independent, financially literate and qualify as Audit Committee Financial Experts. Retain that exact title without adding an unstated separate regulatory attribution.',
        [804,805,806,816,817,818,819,820,821,1242,1243,1244,1245,1246],
        'NAMED_AUDIT_QUALIFICATIONS',current)
    add('Compensation Chair Smith and members Blaylock/Quincey are independent and non-employee directors as defined by Rule16b-3 under the Securities Exchange Act of1934. Interlocks statement expressly covers2022 and proxy date.',
        [823,824,825,833,834,835,836,837,838,1284,1285,1286,1287],
        'NAMED_COMPENSATION_QUALIFICATION',current)
    for title,indexes in [
        ('Governance & Sustainability',[843,844,845,853,854,855,856,857,903,904,905,906,907]),
        ('Regulatory and Compliance',[859,860,861,867,868,869,870,871,872,925,926,927,928,929,930]),
        ('Science and Technology',[874,875,876,877,884,885,886,887,888,889])]:
        add(f'{title} named Chair and additional members are all independent; the cited full roster retains every named person.',
            indexes,'COMPLETE_NAMED_COMMITTEE_ROSTER',current)
    add('No new Directors elected during2022 and no Committee composition changes during2022 are explicit historical disclosures. Twelve current proxy directors/rosters are not automatically a complete December31 snapshot; retain the source time limits. The Board separately reports five new independent Directors since2018 and average tenure seven years.',
        [355,373,797,799,898,3126],'EXPLICIT_HISTORICAL_CHANGE_AND_COUNT',
        'Historical2022/no-change statements and current2023 aggregates remain distinct.')
    body={'record_type':'ISSUE47_PFIZER_FY2022_FULL_SUPPLIED_TEXT_EXECUTOR_REFERENCE',
          'position':'pfizer:2022-12-31','source_filing':doc['source_filing'],
          'raw_asset_id':doc['raw_asset_id'],'document_id':doc['text_document_id'],
          'request_sha256':sha((args.input/'request-body.json').read_bytes()),
          'all_3511_supplied_text_blocks_read':True,'all_3511_raw_spans_verified':True,
          'reading_notes':notes,'reference_units':units,
          'necessary_full_nominee_table_read_and_preserved':table,
          'positive_committee_relations_supported_by_named_text':21,
          'table_font_symbols_interpreted':False,'all_344_tables_read':False,
          'all_media_interpreted':False,
          'unresolved':[
              {'kind':'QUALIFICATION_POLICY','blocks':[364,413,478,496,518,541,724,897,3140],
               'detail':'Issuer skills and suitability/time/energy/role assessments retained with actual speakers. Their qualification-policy acceptance remains pending #28; not simply deemed false.'},
              {'kind':'SYMBOLS_AND_MEDIA','detail':'Table32 l/ü font symbols retained literally; named card/committee texts independently support21 positive committee relations and11 named independent directors. Other skill/demographic charts/media and font rendering not interpreted; no absence from blanks.'},
              {'kind':'TIME','detail':'SummaryasofDecember31,2022 versus currentMarch2023 and late2022 review must remain distinct; no unspecified year-end Board snapshot.'},
              {'kind':'OTHER_BODY_SCOPE','blocks':[995,1000,1493,3239,3330,3337,3445,3485,3510],
               'detail':'EmployeePAC/PCPC/managementSteering, congressional bodies and ProxyCommittee/proxy voting powers remain distinct. Named proxies are not three additional Board appointees; no automatic principal Board-committee credit from the proxy function.'},
              {'kind':'METHOD','detail':'No independent input-only test of this exact request and no target-model execution. This executor reference is not an independent blind answer or a new holdout.'}],
          'complete_c02_acceptance':False,'native_run_created':False,
          'new_acceptances':0,'calls':[0,0,0]}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(body,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'blocks':3511,'reference_units':len(units),'necessary_tables':1,
                      'named_text_committee_relations':21,'calls':[0,0,0]}))


if __name__=='__main__':main()

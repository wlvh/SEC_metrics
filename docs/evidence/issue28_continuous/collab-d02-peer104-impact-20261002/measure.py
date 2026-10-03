"""Run fixed peer's Item 8 rule over #28's ten saved D02 private candidates."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import content_hash
from vnext.text_business_candidates import _LEGAL

PEER = '104876d6cfae7812d93fd5b8a4bb0e0f97959fff'
RULE = 'scripts/vnext/d02_item_8_category_mentions.py'
TERMS = 'catalog/r6/D02_item_8_category_mention_v1.json'
source = subprocess.check_output(['git', 'show', PEER + ':' + RULE],
                                 cwd=ROOT, text=True)
terms = json.loads(subprocess.check_output(['git', 'show', PEER + ':' + TERMS],
                                           cwd=ROOT, text=True))
names = {'_parenthetical_example', '_list_member', 'classify'}
nodes = [node for node in ast.parse(source).body
         if isinstance(node, ast.FunctionDef) and node.name in names]
assert {node.name for node in nodes} == names
namespace = {'re': re,
    '_MENTION': {name: re.compile(pattern, re.I)
                 for name, pattern in terms['category_mention'].items()},
    '_EXPOSURE': tuple((item['name'], re.compile(item['pattern'], re.I))
                       for item in terms['exposure']),
    'TERMS_HASH': content_hash(value=terms)}
exec(compile(ast.Module(body=nodes, type_ignores=[]), RULE, 'exec'), namespace)
classify = namespace['classify']

roots = {
    'marriott_international': 'issue28-marriott-current-36-20260929',
    'southwest_airlines': 'issue28-southwest-current-36-cli-20260929',
    'ford_motor_company': 'issue28-ford_motor_company-current-36-cli-20260929',
    'pfizer': 'issue28-pfizer-current-36-cli-20260929',
    'jpmorgan_chase': 'issue28-jpmorgan_chase-current-36-cli-20260929',
    'salesforce': 'issue28-salesforce-current-36-cli-20261001',
    'lumen_technologies': 'issue28-lumen_technologies-current-36-cli-20260929',
    'macys': 'issue28-macys-current-36-cli-20260929',
    'paramount_skydance_paramount_global':
        'issue28-paramount_skydance_paramount_global-current-36-cli-20260929',
    'enphase_energy': 'issue28-enphase_energy-current-36-cli-20260929'}
assert len(roots) == 10
results = []
for company, dirname in roots.items():
    paths = list((Path('/private/tmp')/dirname).glob(
        'state/**/metrics/D02/attempts/*/runs/D02/records.jsonl'))
    assert len(paths) == 1, (company, paths)
    records_path = paths[0]
    records = [json.loads(line) for line in records_path.read_bytes().splitlines()]
    candidate = next(r for r in records if r['record_type'] ==
                     'DETERMINISTIC_TEXT_CANDIDATE')
    evidence = next(r for r in records if r['record_type'] == 'EVIDENCE_CHECK')
    result = next(r for r in records if r['record_type'] == 'METRIC_RESULT'
                  and r['metric_id'] == 'D02')
    assert evidence['status'] == 'PASS'
    references = {r['source_reference_id']: r for r in records
                  if r['record_type'] == 'SOURCE_REFERENCE'}
    blobs = {r['raw_asset_id']: r for r in records
             if r['record_type'] == 'RAW_BLOB'}
    selected_item8, proposed_exclusions = [], []
    for role, claim in candidate['selected'].items():
        if claim['section_id'] != 'ITEM_8':
            continue
        classification = classify(text=claim['text'], keyword=_LEGAL)
        row = {'block_index': claim['block_index'], 'role': role,
               'text_sha256': hashlib.sha256(claim['text'].encode()).hexdigest(),
               'category_mentions': [x['why'] for x in
                                     classification['occurrences']],
               'exposure': classification['exposure'],
               'prose': classification['prose'],
               'peer_rule_would_exclude': classification['left_out']}
        selected_item8.append(row)
        if classification['left_out']:
            ref = references[claim['source_reference_id']]
            blob = blobs[ref['raw_asset_id']]
            raw = (records_path.parents[2]/'data'/blob['storage_uri']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == ref['raw_asset_id'][7:]
            assert len(raw) == blob['byte_length']
            span = raw[claim['raw_start_byte']:claim['raw_end_byte']]
            assert hashlib.sha256(span).hexdigest() == claim['raw_span_sha256'].removeprefix('sha256:'), (company, claim['block_index'], claim['raw_span_sha256'], hashlib.sha256(span).hexdigest())
            proposed_exclusions.append({**row, 'source_reference_id':
                ref['source_reference_id'], 'raw_asset_id': ref['raw_asset_id'],
                'raw_span_sha256': claim['raw_span_sha256'],
                'text': claim['text']})
    results.append({'company_id': company, 'period_end': result['period_end'],
                    'old_result_id': result['result_id'],
                    'old_selected_count': len(candidate['selected']),
                    'item8_selected_count': len(selected_item8),
                    'item8': selected_item8,
                    'proposed_exclusions': proposed_exclusions,
                    'new_result_created': False})

by_company = {row['company_id']: row for row in results}
assert {row['block_index'] for row in by_company['pfizer']['proposed_exclusions']} >= {2175, 2240}
assert {row['block_index'] for row in by_company['paramount_skydance_paramount_global']['proposed_exclusions']} >= {2257}
assert {row['block_index'] for row in by_company['lumen_technologies']['proposed_exclusions']} >= {1670}
assert 2108 in {row['block_index'] for row in by_company['paramount_skydance_paramount_global']['item8']
                if not row['peer_rule_would_exclude']}
assert 755 not in {row['block_index'] for row in by_company['enphase_energy']['item8']}
body = {'record_type': 'ISSUE28_CURRENT_D02_PEER104_ITEM8_RULE_PILOT',
        'peer_fixed_commit': PEER,
        'peer_rule_git_blob': subprocess.check_output(['git','rev-parse',PEER+':'+RULE],
            cwd=ROOT,text=True).strip(),
        'peer_terms_git_blob': subprocess.check_output(['git','rev-parse',PEER+':'+TERMS],
            cwd=ROOT,text=True).strip(),
        'results': results,
        'total_proposed_exclusions': sum(len(r['proposed_exclusions']) for r in results),
        'new_real_calls': [0, 0, 0],
        'source_review_limit': 'Pilot on ten saved private D02 candidates; rule not wired to #28 or #47 native selection, proposed exclusions need own content assessment; Enphase Item3 footer is outside this rule.',
        'old_result_identities_retained': True,
        'current_390_credit': False}
(HERE/'pilot.json').write_text(json.dumps(body, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'item8_selected':sum(r['item8_selected_count'] for r in results),
    'proposed_exclusions':body['total_proposed_exclusions'],
    'by_company':{r['company_id']:len(r['proposed_exclusions']) for r in results},
    'new_real_calls':[0,0,0]}))

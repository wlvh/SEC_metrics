import json, glob, sys, re
sys.path.insert(0, 'scripts')
import vnext.historical_board_composition_v2 as M
reads = {}
for f in glob.glob('docs/evidence/issue47_history/c02-*/judgements/*.json'):
    j = json.load(open(f)); reads[j['position']] = j
adj = json.load(open('docs/evidence/issue47_history/c02-composition-facts/adjudication.json'))
dec = {(r['position'], r['i']): r for r in adj['decisions']}
orig = M._full_name
lead = re.compile("^[" + M._BULLET_CHARS + "]")
def patched(blocks, k, registrant):
    if lead.match(M.clean(blocks[k]["text"])):
        return None
    return orig(blocks, k, registrant)
for f in sorted(glob.glob(sys.argv[1] + '/*.json')):
    d = json.load(open(f)); doc = d['document']
    base = M.board_composition_facts(document=doc, period_start=d['period_start'])
    M._full_name = patched
    try:
        new = M.board_composition_facts(document=doc, period_start=d['period_start'])
    finally:
        M._full_name = orig
    a = {c['block_index'] for c in base['candidates']}; b = {c['block_index'] for c in new['candidates']}
    j = reads[d['position']]
    v = {x['i']: x['verdict'] for k in ('selected', 'pool_facts', 'outside_pool_facts', 'supplementary') for x in j.get(k, []) or []}
    pool = {x['i'] for x in j.get('pool', [])}
    for i in sorted(b - a):
        dd = dec.get((d['position'], i))
        print(d['position'], 'ADD', i, v.get(i, 'NOT' if i in pool else 'UNREAD'), (dd['rule'] + ':' + dd['decision']) if dd else '-', '|', doc['blocks'][i]['text'][:60])
    for i in sorted(a - b):
        dd = dec.get((d['position'], i))
        print(d['position'], 'DROP', i, v.get(i, 'NOT' if i in pool else 'UNREAD'), (dd['rule'] + ':' + dd['decision']) if dd else '-', '|', doc['blocks'][i]['text'][:60])

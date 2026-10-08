import json, glob, sys
sys.path.insert(0, 'scripts')
import vnext.historical_board_composition_v2 as M
reads = {}
for f in glob.glob('docs/evidence/issue47_history/c02-*/judgements/*.json'):
    j = json.load(open(f)); reads[j['position']] = j
adj = json.load(open('docs/evidence/issue47_history/c02-composition-facts/adjudication.json'))
dec = {(r['position'], r['i']): r for r in adj['decisions']}
orig = M._registrant_title_lines
def patched(blocks, cores, registrant=None):
    taken = orig(blocks, cores)
    out = list(taken)
    for i, _ in taken:
        name = M._card_name(blocks, i, i + 1, patched.registrant)
        if name:
            out.extend((k, "DIRECTOR_NAME") for k in name)
    return out
for f in sorted(glob.glob(sys.argv[1] + '/*.json')):
    d = json.load(open(f)); doc = d['document']
    base = M.board_composition_facts(document=doc, period_start=d['period_start'])
    patched.registrant = M._registrant_keys(doc)
    M._registrant_title_lines = patched
    try:
        new = M.board_composition_facts(document=doc, period_start=d['period_start'])
    finally:
        M._registrant_title_lines = orig
    a = {c['block_index'] for c in base['candidates']}; b = {c['block_index'] for c in new['candidates']}
    j = reads[d['position']]
    v = {x['i']: x['verdict'] for k in ('selected', 'pool_facts', 'outside_pool_facts', 'supplementary') for x in j.get(k, []) or []}
    pool = {x['i'] for x in j.get('pool', [])}
    for i in sorted(b - a):
        dd = dec.get((d['position'], i))
        print(d['position'], 'ADD', i, v.get(i, 'NOT' if i in pool else 'UNREAD'), (dd['rule'] + ':' + dd['decision']) if dd else '-', '|', doc['blocks'][i]['text'][:60])
    for i in sorted(a - b):
        print(d['position'], 'DROP', i)

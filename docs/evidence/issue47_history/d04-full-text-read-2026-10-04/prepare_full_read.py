import hashlib
import json
from pathlib import Path
from collections import defaultdict
from html.parser import HTMLParser

import argparse
p = argparse.ArgumentParser(description='Rebuild all supplied D04 text/native units for this fixed 16-request round, offline; does not judge their semantics.')
p.add_argument('--requests', type=Path, required=True)
p.add_argument('--source-root', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
ROOT, OUT = a.requests, a.out
SOURCE = a.source_root / 'evidence/request_attempts'
OUT.mkdir(exist_ok=False)
docs = defaultdict(lambda: {'blocks': {}, 'facts': {}, 'supplements': [], 'units': [], 'messages': []})
for p in sorted(ROOT.glob('D04-*.messages.json')):
    q = json.loads(json.loads(p.read_text())[1]['content'])
    for u in q['units']:
        d = docs[u['document_id']]
        d['company'] = q['company_id']; d['period_end'] = q['target_period']['period_end']
        d['units'].append({'id': u['unit_id'], 'kind': u['kind'], 'ordinal': u['ordinal'],
                           'payload_sha256': u['payload_sha256'], 'request': p.stem.split('.')[0]})
        d['messages'].append({'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        payload = u['payload']; layout = payload.get('row_layout', {})
        for k, row in payload.get('blocks', {}).items():
            assert int(k) not in d['blocks']
            d['blocks'][int(k)] = dict(zip(layout['columns'], row))
        for k, row in payload.get('facts', {}).items():
            assert int(k) not in d['facts']
            f = dict(zip(layout['columns'], row))
            f['fact'] = dict(zip(layout['fact_columns'], f['fact']))
            d['facts'][int(k)] = f
        d['supplements'].extend(payload.get('objects', []))

index = []
for position, (did, d) in enumerate(docs.items()):
    assert sorted(d['blocks']) == list(range(len(d['blocks'])))
    candidates = list(SOURCE.glob('*/*/mar-*.htm')) if d['company'] == 'marriott_international' else list(SOURCE.glob('*/*/para-20241231.htm')) + list(SOURCE.glob('*/*/d886907d10ka.htm'))
    matches = []
    for p in candidates:
        raw = p.read_bytes()
        if all(hashlib.sha256(raw[b['raw_start_byte']:b['raw_end_byte']]).hexdigest() == b['raw_span_sha256'] for b in d['blocks'].values()):
            matches.append((p, raw))
    assert len(matches) == 1, (did, len(matches))
    raw_path, raw = matches[0]
    label = f'{position:02d}-{d["company"]}-{d["period_end"]}-{raw_path.name}'
    packets = []; lines = []; count = 0; start = 0
    for k, block in sorted(d['blocks'].items()):
        line = f'B{k}: {block["text"]}\n'
        if lines and count + len(line) > 36000:
            name = f'{label}-visible-{len(packets):02d}.txt'
            (OUT/name).write_text(''.join(lines)); packets.append({'file': name, 'first_block': start, 'last_block': k-1,
               'sha256': hashlib.sha256((OUT/name).read_bytes()).hexdigest()})
            lines = []; count = 0; start = k
        lines.append(line); count += len(line)
    name = f'{label}-visible-{len(packets):02d}.txt'
    (OUT/name).write_text(''.join(lines));packets.append({'file': name, 'first_block': start, 'last_block': len(d['blocks'])-1,
        'sha256': hashlib.sha256((OUT/name).read_bytes()).hexdigest()})
    (OUT/(label+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=1)+'\n')
    concepts = sorted({(tuple(f['expanded_concept']),f['fact']['tag']) for f in d['facts'].values()})
    (OUT/(label+'-native-concepts.txt')).write_text('\n'.join(f'{concept} | {tag}' for concept,tag in concepts)+'\n')
    index.append({'label':label,'document_id':did,'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest(),
                  'raw_path':str(raw_path),'blocks':len(d['blocks']),'facts':len(d['facts']),
                  'supplement_objects':len(d['supplements']),'units':d['units'],'packets':packets,
                  'all_block_raw_spans_authenticated': True})
(OUT/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=1)+'\n')
print(json.dumps([{k:d[k] for k in ('label','blocks','facts','supplement_objects')} | {'visible_packets':len(d['packets'])} for d in index],indent=1))

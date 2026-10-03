import sys,json,pathlib,hashlib,re
sys.path.insert(0,'/Users/lyuhongwang/Developer/SEC_metrics/scripts')
from vnext.deterministic_router import parse_accession_xbrl_source,_visible_text
from vnext.b06_disclosure import tables,origins
base=pathlib.Path('/tmp/sec_metrics_issue28_continuous/v14-ten-company-34-1c9f562')
out=pathlib.Path('/tmp/sec_metrics_issue28_continuous/pfizer-b06-note-census');out.mkdir(exist_ok=True)
records=[json.loads(x) for x in (base/'runs/pfizer/B06/records.jsonl').read_text().splitlines()]
manifest=json.loads((base/'runs/pfizer/B06/manifest.json').read_text())
ref=next(x for x in manifest['source_references'] if x['document_name'].endswith('.xml'))
blob=next(x for x in records if x['record_type']=='RAW_BLOB' and x['raw_asset_id']==ref['raw_asset_id'])
p=base/'data/pfizer'/blob['storage_uri'];raw=p.read_bytes();assert 'sha256:'+hashlib.sha256(raw).hexdigest()==ref['raw_asset_id']
parsed=parse_accession_xbrl_source(raw_bytes=raw);rows=[]
for f in parsed.facts:
 c=parsed.contexts[f['context_ref']]
 if c['period_end']!='2025-12-31':continue
 if 'textblock' not in f['qualified_name'].lower() or not re.search(r'debt|borrow|lease|credit|financ',f['qualified_name'],re.I):continue
 text=_visible_text(raw_bytes=f['text'].encode());grid=tables(f['text'])
 d={'ordinal':f['ordinal'],'concept':f['qualified_name'],'context':{**c,'dimensions':dict(c['dimensions'])},'text_length':len(text),'tables':len(grid),'text':text,
    'table_rows':[[' | '.join(v['text'] for v in origins(r)) for r in t['rows']] for t in grid]}
 (out/(str(f['ordinal'])+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));rows.append({k:v for k,v in d.items() if k not in ['text','table_rows']})
 print(d['ordinal'],d['concept'],c['period_start'],c['dimensions'],d['text_length'],d['tables'],text[:180])
(out/'index.json').write_text(json.dumps({'source_reference':ref,'raw_blob':blob,'notes':rows,'calls':{'provider':0,'paid':0,'sec':0}},indent=2))

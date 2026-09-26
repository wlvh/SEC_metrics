import sys,pathlib,json
sys.path[:0]=['.','scripts']
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.financial_structured import _InlineTableIndex,_fact_cells
from vnext.text_results_v2 import _ReportedFactMetadata
from vnext.b06_combined_borrowings import POLICY
base=pathlib.Path('/tmp/sec_metrics_issue28_continuous/v14-ten-company-34-1c9f562');recs=[json.loads(x) for x in (base/'runs/pfizer/B06/records.jsonl').read_text().splitlines()]
ref=next(r for r in recs if r['record_type']=='SOURCE_REFERENCE' and r['document_name']=='pfe-20251231.htm');blob=next(r for r in recs if r['record_type']=='RAW_BLOB' and r['raw_asset_id']==ref['raw_asset_id']);raw=(base/'data/pfizer'/blob['storage_uri']).read_bytes()
p=parse_accession_xbrl_source(raw_bytes=raw);m=_ReportedFactMetadata();m.feed(raw.decode());m.close();index=_InlineTableIndex(raw);index.feed(raw.decode());index.close()
names={x.casefold() for x in POLICY['source_monetary_concepts'].values()}
fs=[f for f in p.facts if m.facts[f['ordinal']]['concept'][1].casefold() in names and not p.contexts[f['context_ref']]['dimensions'] and p.contexts[f['context_ref']]['period_start']==p.contexts[f['context_ref']]['period_end']=='2025-12-31']
cells=_fact_cells(index,p,{f['ordinal'] for f in fs})
for f in fs:
 pos=index.fact_positions[f['ordinal']]
 print(f['ordinal'],f['qualified_name'],f['text'],'HAS_CELL',f['ordinal'] in cells,'ATTRS',m.facts[f['ordinal']]['attrs'])
 if f['ordinal'] in cells: print('CELL_TEXT',repr(cells[f['ordinal']][1]['text']))
 else: print(raw[max(pos-150,0):pos+500].decode())

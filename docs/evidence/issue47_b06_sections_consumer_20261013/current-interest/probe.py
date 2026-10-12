"""Inspect original current-interest location; do not infer debt inclusion."""
import argparse,json,re,socket
from pathlib import Path
from unittest.mock import patch
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext.fiscal_year_labels import _DefinitionBlocks
from vnext.deterministic_router import parse_accession_xbrl_source
from vnext.financial_structured import _InlineTableIndex,_fact_cells
from vnext.text_results_v2 import _ReportedFactMetadata
from vnext.normal_annual_input_v2 import exact_json_value
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=a.source_root.resolve();output=a.output.resolve();assert not output.exists()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')):
 selected=prepare_selected_debt_sources(repo_root=source,company_id='macys',fiscal_year=2024);records={}
 for kind in ('primary','xml'):
  src=selected['preparation'][kind];raw=src['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close();facts=[f for f in parsed.facts if f['qualified_name'].split(':')[-1]=='InterestPayableCurrent' and parsed.contexts[f['context_ref']]['period_end']=='2025-02-01'];rows=[]
  if kind=='primary':
   index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close();cells=_fact_cells(index,parsed,{f['ordinal'] for f in facts})
  for f in facts:
   row={'fact':f,'context':parsed.contexts[f['context_ref']],'metadata':meta.facts[f['ordinal']]}
   if kind=='primary' and f['ordinal'] in cells:
    table,cell=cells[f['ordinal']];row.update(table=table,cell=cell)
   rows.append(row)
  records[kind]={'source_reference':src['source_reference'],'facts':rows}
 primary=selected['preparation']['primary']['raw_bytes'];blocks=_DefinitionBlocks(primary.decode('utf-8-sig'));blocks.feed(primary.decode('utf-8-sig'));blocks.close();blocks._flush();near=[{'index':i,'block':b,'neighbors':[blocks.blocks[j] for j in range(max(0,i-2),min(len(blocks.blocks),i+3))]} for i,b in enumerate(blocks.blocks) if re.search(r'interest payable|accounts payable and accrued|accrued interest',b['text'],re.I)]
 result=exact_json_value({'record_type':'B06_REPORTED_CURRENT_INTEREST_SOURCE_RELATION_INVESTIGATION','source_records':records,'nearby_blocks':near,'definition':json.loads(Path('config/b06_bond_debt_set_v1.json').read_text())['debt_scope_definition'],'new_calls':[0,0,0]});output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
 for kind,src in result['source_records'].items():print(kind,[(r['fact']['ordinal'],r['fact']['text'],r['context']['period_start'],r['context']['period_end']) for r in src['facts']])
 for r in result['nearby_blocks']:print(r['index'],r['block']['text'][:1000])

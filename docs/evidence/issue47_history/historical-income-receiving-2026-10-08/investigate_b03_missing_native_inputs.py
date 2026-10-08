import json,re,time,socket
from pathlib import Path
from unittest.mock import patch
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.deterministic_router import parse_accession_xbrl_source,shared_xbrl_parses
from vnext.text_results_v2 import _ReportedFactMetadata,_verified_context
from vnext.governance_signals import _source_value
from vnext.financial_structured import _InlineTableIndex,_fact_cells
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE,is_fasb_namespace
root=Path.cwd();source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');base=root/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08';company='marriott_international';output={};start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')),shared_xbrl_parses():
 for year in [2021,2022,2023]:
  selection=resolve_period_selection(repo_root=source,company_id=company,fiscal_year=year,rules_root=root)
  annual=prepare_historical_annual_input(repo_root=source,company_id=company,period_selection=selection,rules_root=root);reader=_Sources(source,company,annual['entity']);s=reader.primary(annual['filing']);raw=s['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode('utf8'));meta.close();period=annual['table_input']['target_period'];rows=[]
  for fact in parsed.facts:
   info=meta.facts[fact['ordinal']];uri,name=info['concept'];c=parsed.contexts[fact['context_ref']]
   if not re.search('depreciat|amortiz',name,re.I) or c['period_start']!=period['period_start'] or c['period_end']!=period['period_end'] or str(int(c['entity_identifier']))!=str(int(annual['entity'])):continue
   if not is_fasb_namespace(uri,namespace_policy=YEAR_OR_DATE_RELEASE):continue
   proof=_verified_context(native={**c,'dimensions':dict(c['dimensions'])},metadata=meta)
   rows.append({'ordinal':fact['ordinal'],'concept':info['concept'],'value':_source_value(fact,info),'scale':fact['scale'],'decimals':info['attrs'].get('decimals'),'context_ref':fact['context_ref'],'context_proof':proof,'unit':meta.units.get(fact['unit_ref']),'text':fact['text']})
  index=_InlineTableIndex(raw);index.feed(raw.decode('utf8'));index.close();cells=_fact_cells(index,parsed,{r['ordinal'] for r in rows})
  for r in rows:
   bound=cells.get(r['ordinal'])
   if bound:
    table,cell=bound;r['cell']={**{k:cell.get(k) for k in ['row_index','column_index','rowspan','colspan','text','raw_text']},'table_id':table['table_id']}
  output[str(year)]={'filing':annual['filing'],'period':period,'source_reference':s['source_reference'],'rows':rows}
record={'record_type':'B03_OLDER_PRIMARY_NATIVE_INPUT_CENSUS','company':company,'seconds':time.monotonic()-start,'years':output,'classification':'candidate census only; dimensions/rows do not by themselves prove additive full-scope D&A','calls':{'sec':0,'provider':0,'paid':0}}
(base/'older-native-da-census.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({y:[{'concept':r['concept'][1],'value':r['value'],'dims':[(d['dimension_qname'],d['member_qname']) for d in r['context_proof']['dimensions']],'cell':r.get('cell',{}).get('table_id')} for r in o['rows']] for y,o in output.items()},ensure_ascii=False))

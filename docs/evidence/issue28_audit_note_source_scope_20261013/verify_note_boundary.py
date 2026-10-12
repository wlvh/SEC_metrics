"""Full saved-source successor note boundary, not financial-input approval."""
import argparse,json,socket,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.normal_governance_input import _Sources
from vnext.normal_period_selection import resolve_period_selection
from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
from vnext.normal_annual_input_v2 import exact_json_value
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No live source/provider')):
 selection=resolve_period_selection(repo_root=a.source_root,company_id='marriott_international',fiscal_year=2021)
 reader=_Sources(a.source_root,'marriott_international','1048286')
 def source(filing):
  item=next(s for s in reader.auditor_filing(filing) if s['raw_blob']['media_type']=='text/html')
  return {'raw':item['raw_bytes'],'blob':item['raw_blob'],'reference':item['source_reference'],'filing':filing}
 result=inspect_annual_amendment_scope(original=source(selection['prior_filing']),amendment=source(selection['prior_amendments'][0]),
   company_id='marriott_international',cik='1048286',note_layout='inline-paragraphs-v2',namespace_policy=YEAR_QUARTER_OR_DATE)
 result=exact_json_value(result)
 assert result['classification']=='UNRESOLVED'
 assert result['original_statement_admission_requires_further_review']
 assert 'ORIGINAL_STATEMENT_VALUES' not in result['unchanged_input_classes']
 assert result['explanatory_note']['end']-result['explanatory_note']['start']==3
 summary={'elapsed_seconds':time.monotonic()-start,'classification':result['classification'],
   'issues':result['issues'],'note_start':result['explanatory_note']['start'],'note_end':result['explanatory_note']['end'],
   'note_text':result['explanatory_note']['text'],'unchanged_input_classes':result['unchanged_input_classes'],
   'original_statement_admission_requires_further_review':True,'scope_id':result['scope_id'],'calls':[0,0,0]}
 a.output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))

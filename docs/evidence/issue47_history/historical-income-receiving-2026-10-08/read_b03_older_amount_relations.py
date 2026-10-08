import json,re,time,socket,hashlib
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.composite_scope import index_source_structure
root=Path.cwd();base=root/'docs/evidence/issue47_history/historical-income-receiving-2026-10-08';source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');census=json.load(open(base/'older-native-da-census.json'));out={};start=time.monotonic()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')):
 for year,data in census['years'].items():
  reader=_Sources(source,'marriott_international','1048286');s=reader.primary(data['filing']);raw=s['raw_bytes'];structure=index_source_structure(source_bytes=raw)
  rows=[]
  for block in structure['blocks']:
   if re.search(r'\b(?:depreciation|amortization)\b',block['visible_text'],re.I):rows.append({k:block[k] for k in ['start_byte','end_byte','span_sha256','inside_table','visible_text']})
  out[year]={'source_reference':s['source_reference'],'source_sha256':hashlib.sha256(raw).hexdigest(),'paragraphs':rows}
record={'seconds':time.monotonic()-start,'years':out,'scope':'complete paragraphs containing D&A wording; no numeric inclusion decision or source changes','new_calls':{'sec':0,'provider':0,'paid':0}}
(base/'older-da-wording.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
for year,data in out.items():
 print('FY'+year)
 for block in data['paragraphs']:
  print(block['visible_text'])

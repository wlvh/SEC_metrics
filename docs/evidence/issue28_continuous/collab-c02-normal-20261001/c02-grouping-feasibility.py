"""Structural only: can full selected C02 blocks be grouped with nearby context?"""
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from vnext.canonical import content_hash,sha256_file
from vnext.normal_run_v3 import prepare_case
from vnext.c02_composition_text_results import _prepared
CENSUS=json.load(open(HERE/'c02-capacity-census.json'))
log=ROOT/'evidence/requests_log.csv';before=sha256_file(path=log)
rows=[];signal.alarm(110)
with (patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')),
      patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')),
      patch('sec_http.urlopen',side_effect=AssertionError('HTTP_FORBIDDEN'))):
 for census in CENSUS['companies']:
  if census['status']!='SOURCE_PROPOSAL_READY':continue
  company=census['company_id']
  case=prepare_case(data_root=ROOT,company_id=company,metric_id='C02',c02_composition=True)
  prepared=_prepared(**{k:v for k,v in case['text_arguments'].items() if k!='compiled_spec'})
  sid,p=next((sid,p) for sid,p in prepared['proposals'].items() if p.get('metric_id')=='C02')
  doc=prepared['documents'][sid]
  selected=[v['block_index'] for v in p['candidates']]
  assert len(selected)==census['candidate_count'] and len(selected)==len(set(selected))
  assert content_hash(value=selected)==census['candidate_indexes_hash']
  groups=[]
  for i in selected:
   if not groups or i-groups[-1][-1]>3:groups.append([i])
   else:groups[-1].append(i)
  spans=[(g[0],g[-1]) for g in groups]
  assert all(spans[i][1]<spans[i+1][0] for i in range(len(spans)-1))
  expanded=[[doc['blocks'][i]['text'] for i in range(lo,hi+1)] for lo,hi in spans]
  texts=['\n'.join(parts) for parts in expanded]
  original={i for i in selected};covered={i for lo,hi in spans for i in range(lo,hi+1)}
  assert original <= covered
  extra=sorted(covered-original)
  rendered=sum(map(len,texts))+max(0,len(texts)-1)
  row={'company_id':company,'original_selected_count':len(selected),'group_count_if_gap_at_most_two':len(groups),
       'group_rendered_chars':rendered,'largest_group_chars':max(map(len,texts)),
       'context_only_blocks_included':len(extra),'context_only_chars':sum(len(doc['blocks'][i]['text']) for i in extra),
       'group_spans_hash':content_hash(value=spans),
       'group_selected_indexes_hash':content_hash(value=groups),
       'extra_context_indexes_hash':content_hash(value=extra),
       'fits_64_items':len(groups)<=64,'fits_64000_chars':rendered<=64000,
       'source_document_id':doc['text_document_id'],'source_reference_id':sid}
  rows.append(row)
  print(json.dumps(row,sort_keys=True),flush=True)
assert before==sha256_file(path=log)
out={'record_type':'ISSUE28_C02_GROUPING_STRUCTURAL_FEASIBILITY','code_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     'rule':'Group consecutive selected blocks, bridging at most two complete intervening source blocks and including their visible text; no source block is deleted or silently reclassified.',
     'rows':rows,'source_log_unchanged':True,'new_real_calls':[0,0,0],
     'limit':'Offline structural estimate only: does not establish canonical composite document identity, native Evidence/Run replay, semantic relevance of added context, or content acceptance.'}
(HERE/'c02-grouping-feasibility.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

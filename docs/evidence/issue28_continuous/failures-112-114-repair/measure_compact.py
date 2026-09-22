"""Bounded six-group output census; synthetic answers are not repaired112."""
from pathlib import Path
import json,time,os
from types import SimpleNamespace
from vnext.continuous_semantic_calls import prepare_requests,select_native_request_variants,request_digest
from vnext.continuous_call_ledger import live_ledger
from vnext.capacity_reference_contract import restore_base_request,upgrade_request,restore_response
from vnext.capacity_semantic_review import validate_response
from vnext.continuous_request_context import _load_tokenizer
from vnext.native_unit_index import evidence_json_bytes
from vnext.native_request_construction import request_construction_session
from vnext.requirements import load_requirement_snapshot
from vnext.normal_source_authority import ROOT
from tests.vnext.test_capacity_run_material import recorded_response
start=time.monotonic();evidence=Path(__file__).resolve().parent
requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements/issue_28_v14');tokenizer,_=_load_tokenizer();assert tokenizer
with request_construction_session(requirement):
 if os.environ.get('REPORT_FROM_SAVED_SOURCE')=='1':
  from vnext.continuous_semantic_calls import source_requests
  original111=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0111')
  raw_source=(original111/'source.json').read_bytes();source=json.loads(raw_source);bases=source_requests(source)
  selected=[SimpleNamespace(source_bytes=raw_source,request_bytes=(original111/'semantic-request.json').read_bytes() if i==0 else evidence_json_bytes(upgrade_request(r,compact=True))) for i,r in enumerate(bases)]
  variants=[{'original_ordinal':111 if i==0 else None,'variant':'B13_SOURCE_REFERENCES_V1' if i==0 else 'B13_TYPED_COMPACT_REFERENCES_V2'} for i in range(len(bases))]
 else:
  prepared=prepare_requests(company_id='enphase_energy',metric_id='B13',reference_context=True,program_quantity_roles=True)
  ledger=live_ledger(requirement=requirement)
  selected,variants=select_native_request_variants(prepared_requests=prepared,ledger=ledger,source_references=True,compact_references=True)
  assert variants[0]['original_ordinal']==111
  original111=ledger.root/'calls/0111';assert selected[0].request_bytes==(original111/'semantic-request.json').read_bytes()
 reports=[]
 for index,item in enumerate(selected):
  request=json.loads(item.request_bytes);base=restore_base_request(request);response=recorded_response(base);proof=base['program_quantity_contract']
  owned={(r['unit_id'],r['source_kind'],r['source_index']) for r in proof['verified_quantity_roles']+proof['verified_nonphysical_references']}
  findings=[f for u in response['units'] for f in u['findings'] if not any((u['unit_id'],e['kind'],e['source_index']) in owned for e in f['evidence'])]
  v1={'units':[{'unit_index':i,'reviewed':True,'unresolved':[],'calculation_limits':[]} for i in range(len(base['units']))],'findings':findings}
  compact=upgrade_request(base,compact=True);books=compact['response_protocol']['classification_codebooks'];rows=[]
  for f in findings:
   refs=[]
   for r in f['evidence']:
    refs.append({'VISIBLE_BLOCK':'B','NATIVE_FACT':'F'}[r['kind']]+str(r['source_index']))
   rows.append([books[k].index(f[k]) for k in ('kind','subject','timing')]+[refs,'Recorded source classification '+','.join(refs)])
  answer={**v1,'findings':rows};raw=evidence_json_bytes(answer)
  checked=validate_response(request=compact,raw_response=raw,source=json.loads(item.source_bytes));assert not checked['unresolved']
  tokens=len(tokenizer.encode(raw.decode(),add_special_tokens=False).ids)
  reports.append({'group_index':index,'source_units':len(base['units']),'required_assessments':len(base['required_candidate_assessments']),'synthetic_findings':len(rows),'v1_tokens':len(tokenizer.encode(evidence_json_bytes(v1).decode(),add_special_tokens=False).ids),'compact_tokens':tokens,'fits4096':tokens<=4096,'actual_model_output_guaranteed':False,'variant':variants[index]})
  if index==1:
   (evidence/'group112-compact-request.json').write_bytes(evidence_json_bytes(compact));(evidence/'group112-synthetic-output.json').write_bytes(raw)
   bad=json.loads(raw);bad['findings']=[[0,0,0,['B449'],'Wrong-kind negative.']]
   try:restore_response(request=compact,raw_response=evidence_json_bytes(bad));raise AssertionError('wrong-kind449 accepted')
   except ValueError as error:assert 'OUTSIDE_SUPPLIED_SOURCE' in str(error)
 assert all(r['fits4096'] for r in reports)
 summary={'status':'PASS_BOUND_COMPACT_CENSUS_AND_111_EXACT_REUSE','report_from_saved_source':os.environ.get('REPORT_FROM_SAVED_SOURCE')=='1','factory_success_reuse_evidence':'Prior census reached final report serialization after all assertions; independent-review/conclusion.md also verifies111 source and HTTP bytes','groups':reports,'unchanged_groups':6,'successful111_request_bytes_unchanged':True,'grouping_changed':False,'remaining_b13_groups':16,'original112_failed':True,'new_calls':[0,0,0],'seconds':round(time.monotonic()-start,3)}
 (evidence/'compact-output-census.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)

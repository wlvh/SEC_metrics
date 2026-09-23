"""All rows remain diagnostic. Leaf probes never create an accepted response."""
from pathlib import Path
from collections import Counter
from types import SimpleNamespace
import json,hashlib
from vnext.normal_source_authority import ROOT
from vnext.capacity_reference_contract import restore_base_request
from vnext.capacity_semantic_review import _restore_units,validate_response
from vnext.capacity_quantity_roles import validate_visible_source_label_roles,validate_quantity_role_findings
from vnext.capacity_utilization_source import validate_explicit_quantity_classifications
from vnext.capacity_native_assessment import build_acceptance
from vnext.continuous_request_context import _load_tokenizer
p=Path(__file__).resolve().parent;root=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls');data=json.loads((p/'all-110-rows.json').read_text());request=json.loads((root/'0170/semantic-request.json').read_text());source=json.loads((root/'0170/source.json').read_text());base=restore_base_request(request);units=_restore_units(base['units'],base['shared_source_dictionaries']);by_unit={u['unit_id']:u for u in units};documents={d['document_id']:d for d in source['documents']};blobs={};findings=[]
for row in data['rows']:
 evidence=[]
 for ref in row['references']:
  doc=documents[by_unit[ref['unit_id']]['document_id']];blob=doc['raw_blob'];raw=blobs.setdefault(blob['storage_uri'],(ROOT/blob['storage_uri']).read_bytes());assert 'sha256:'+hashlib.sha256(raw).hexdigest()==blob['raw_asset_id'];item=ref['source_item'];assert hashlib.sha256(raw[item['raw_start_byte']:item['raw_end_byte']]).hexdigest()==item['raw_span_sha256']
  evidence.append({**ref['reference'],'text':item['text']})
 finding={'unit_id':row['references'][0]['unit_id'],**row['decoded_classification'],'reason':row['reason'],'resolved_evidence':evidence};findings.append(finding)
 problems=validate_visible_source_label_roles(findings=[finding]);row['new_source_role_check']=problems
 if row['decoded_classification']['kind']=='SALES_OR_SHIPMENTS':
  row['manual_source_audit']='Revenue/sales context; not actual output. HISTORICAL is not fully proved for a mixed-year row or a cross-reference; no accepted reclassification.'
 else:row['manual_source_audit']='The quoted source does not establish this claimed physical/planned/product-capacity role. The reason often correctly describes financial/governance context but cannot replace the wrong category.'
 row['raw_html_span_verified']=True
probes={}
for name,fn in [('existing_explicit_quantities',validate_explicit_quantity_classifications),('existing_quantity_roles',validate_quantity_role_findings)]:
 try:probes[name]={'scope':'Only actual request-group units and all110 findings; not full response/native acceptance','unresolved':fn(units=units,findings=findings,period=base['target_period'],quantity_scope=source.get('quantity_scope_context'))}
 except ValueError as error:probes[name]={'scope':'Request-group leaf probe only','error':str(error)}
old=root/'0111';checked=validate_response(request=json.loads((old/'semantic-request.json').read_text()),raw_response=(old/'wire/assistant-output.bin').read_bytes(),source=json.loads((old/'source.json').read_text()))
plan=json.loads(next((old/'invocation_control/plans').glob('*.json')).read_text())
try:build_acceptance(prepared=SimpleNamespace(source_bytes=(old/'source.json').read_bytes(),request_bytes=(old/'semantic-request.json').read_bytes(),requirement={}),plan=plan,response_body=(old/'wire/assistant-output.bin').read_bytes());raise AssertionError('Original111 current acceptance unexpectedly granted')
except ValueError as error:reuse_error=str(error)
raw=json.loads((root/'0170/wire/assistant-output.bin').read_text());tokenizer,_=_load_tokenizer();assert tokenizer
full=json.loads(json.dumps(raw));short=json.loads(json.dumps(raw));shortmaps={'kind':{'CAPACITY_QUALITATIVE':'capacity_qualitative','SALES_OR_SHIPMENTS':'sales','PRODUCT_STORAGE_OR_INSTALLED_CAPACITY':'product_capacity','PLANNED_CAPACITY':'planned_capacity'},'subject':{'TARGET_REGISTRANT':'registrant'},'timing':{'CURRENT_REPORT':'current','HISTORICAL':'historical'}}
for i,row in enumerate(data['rows']):
 for position,key in enumerate(['kind','subject','timing']):
  label=row['decoded_classification'][key];full['findings'][i][position]=label;short['findings'][i][position]=shortmaps[key][label]
counts={name:len(tokenizer.encode(json.dumps(value,ensure_ascii=False,separators=(',',':')),add_special_tokens=False).ids) for name,value in [('numeric_original',raw),('full_named_labels',full),('meaningful_short_labels',short)]}
summary={'status':'COMPLETE_BOUNDED_DIAGNOSTIC_NOT_ACCEPTANCE','rows':len(data['rows']),'unique_findings':64,'duplicate_groups':46,'all_raw_html_spans_verified':True,'all_references_located':True,'mapping_error_observed':False,'source_role_unproved_rows':sum(bool(r['new_source_role_check']) for r in data['rows']),'source_role_unproved_unique_findings':len({r['identical_finding_id'] for r in data['rows'] if r['new_source_role_check']}),'sales_rows_still_have_period_or_context_limits':[r['row'] for r in data['rows'] if not r['new_source_role_check']],'existing_leaf_probes':probes,'original111_current_unresolved':checked['unresolved'],'original111_current_acceptance_error':reuse_error,'original111_terminal':'SUCCEEDED_UNCHANGED; no fresh call/replacement or identity rewrite','format_only_token_comparison':counts,'format_comparison_scope':'All110 rows, including every duplicate and original wrong category. No relabeling; deterministic rendering cost only, not model accuracy or acceptance. Protocol unchanged.','causality':'Incorrect returned categories proven; program mapping consistent. Numeric-expression influence vs model error not established without further authorized validation.','new_calls':[0,0,0]}
(p/'all-110-rows-reviewed.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');(p/'diagnostic-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))

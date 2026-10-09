"""Read-only three-source regression; no model, network, or saved result credit."""
import argparse,json,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
from vnext.b03_contract_amortization_scope import _visible_revenue_deductions
from vnext.deterministic_router import parse_accession_xbrl_source,_numeric_xbrl_value
from vnext.text_results_v2 import _ReportedFactMetadata,_verified_context
from vnext.canonical import sha256_bytes
from vnext.annual_sources import _rows
from vnext.request_bindings import validate_request_attempt_binding
from sec_http import request_log_attempt_id

a=argparse.ArgumentParser();a.add_argument('--source-root',required=True);a.add_argument('--base-sha',required=True);args=a.parse_args()
root=Path(args.source_root).resolve();result=[]
old={'__name__':'vnext._original_scope','__package__':'vnext'}
exec(compile(subprocess.check_output(['git','show',args.base_sha+':scripts/vnext/b03_contract_amortization_scope.py'],text=True),'<fixed-original-scope>','exec'),old)
for year in (2021,2022,2023):
 paths=list((root/'evidence/request_attempts').glob('*/*/mar-'+str(year)+'1231.htm'))
 assert len(paths)==1,(year,paths)
 raw=paths[0].read_bytes();digest=sha256_bytes(content=raw)
 matches=[(i,r) for i,r in enumerate(_rows(root)) if r['document_name']==paths[0].name
          and r['content_sha256']==digest and r['status_code']=='200' and not r['error']]
 assert matches,(year,'source request row missing')
 i,row=matches[-1]
 proof=validate_request_attempt_binding(repo_root=root,source_url=row['source_url'],accession=row['accession'],
     document_name=row['document_name'],content_sha256=digest,request_attempt_id=request_log_attempt_id(row_index=i,row=row),require_immutable=False)
 assert proof['request_repo_relative_path']==str(paths[0].relative_to(root))
 parsed=parse_accession_xbrl_source(raw_bytes=raw);m=_ReportedFactMetadata();m.feed(raw.decode('utf-8-sig'));m.close()
 amounts=[]
 for f in parsed.facts:
  uri,concept=m.facts[f['ordinal']]['concept'];c=parsed.contexts[f['context_ref']]
  if concept!='CapitalizedContractCostAmortization' or c['period_end']!=str(year)+'-12-31' or c['period_start']!=str(year)+'-01-01':continue
  assert int(c['entity_identifier'])==1048286 and c['typed_dimension_count']==0
  assert m.units[f['unit_ref']]=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
  resolved=_verified_context(native={**c,'dimensions':dict(c['dimensions'])},metadata=m)
  def qname(q):
   uri,name=q
   if '/srt/' in uri:return 'srt:'+name
   if '/us-gaap/' in uri:return 'us-gaap:'+name
   return 'mar:'+name
  amounts.append({'ordinal':f['ordinal'],'dimensions':dict(c['dimensions']),
     'resolved_dimensions':{qname(x['dimension_qname']):qname(x['member_qname']) for x in resolved['dimensions']},
     'value_usd':str(_numeric_xbrl_value(text=f['text'],scale=f['scale'],sign=f['sign']))})
 original_relations=old['_visible_revenue_deductions'](raw=raw,parsed=parsed,amounts=amounts,period={'period_end':str(year)+'-12-31'})
 relations=_visible_revenue_deductions(raw=raw,parsed=parsed,amounts=amounts,period={'period_end':str(year)+'-12-31'})
 result.append({'year':year,'primary_source_sha256':digest,'source_proof':proof,'amounts':amounts,
    'original_relations':original_relations,'relations':relations,'all_four_original_facts_retained':relations is not None and len(relations)==len(amounts)==4,
    'B03_complete_or_released':False})
print(json.dumps({'code_root':str(Path(__file__).resolve().parents[3]),'years':result,'new_calls':[0,0,0]},indent=2))

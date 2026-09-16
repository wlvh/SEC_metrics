"""Native parser source probes; clear synthetic SEC-shaped raw, no acquisition."""
from pathlib import Path
from copy import deepcopy
import json
from tests.vnext.test_capacity_utilization_source import quantity_source
from tests.vnext.test_capacity_program_roles import answer,acceptance
from vnext.r6_semantic_source import _native_units
from vnext.capacity_semantic_source import native_capacity_roles
from vnext.capacity_semantic_review import requests_from_source
from vnext.capacity_program_roles import program_source,quantity_contract
from vnext.canonical import content_hash
rows=[]
for name,body,expect in [
 ('physical_qname','<ix:hidden xmlns:issuer="https://issuer.example/2025"><xbrli:unit id="u"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit><ix:nonFraction name="issuer:ProductionQuantity" contextRef="annual" unitRef="u" decimals="0">80</ix:nonFraction></ix:hidden>',False),
 ('monetary_native','<ix:hidden xmlns:us-gaap="http://fasb.org/us-gaap/2025" xmlns:iso="http://www.xbrl.org/2003/iso4217"><xbrli:unit id="u"><xbrli:measure>iso:USD</xbrli:measure></xbrli:unit><ix:nonFraction name="us-gaap:LineOfCreditFacilityMaximumBorrowingCapacity" contextRef="annual" unitRef="u" decimals="0">100</ix:nonFraction></ix:hidden>',True),
 ('physical_supplement','<ix:continuation id="supplement"><p>For fiscal year 2025, we produced 80 widgets worldwide.</p></ix:continuation>',False)]:
 s,raw=quantity_source(body);document=s['documents'][0];native,coverage=_native_units(next(iter(raw.values())),{'document':{'text_document_id':document['document_id']}})
 s['units']+=native;s['required_unit_ids']=[u['unit_id']for u in s['units']];document['source_unit_ids']=s['required_unit_ids'];document['native_coverage']=coverage
 # Actual parser facts keep the source ordinal. All units, including DEI, remain.
 s['native_capacity_role_assessments']=native_capacity_roles(s['units']);s['capacity_navigation']=[]
 for u in native:
  if u['kind']=='NATIVE_FACTS':
   for r in u['payload']['facts']:
    if r['fact']['qualified_name'].endswith(('ProductionQuantity','LineOfCreditFacilityMaximumBorrowingCapacity')):s['capacity_navigation'].append({'unit_id':u['unit_id'],'kind':'NATIVE_FACT','source_index':r['fact']['ordinal']})
 s['semantic_source_id']=content_hash(value={k:v for k,v in s.items()if k!='semantic_source_id'});s=program_source(s)
 requests=requests_from_source(s);outcomes=[]
 for q in requests:
  response=answer(q)
  if name=='physical_qname':
   for row in response['units']:
    row['findings']=[{'kind':'OTHER_CONTEXT','subject':'TARGET_REGISTRANT','timing':'CURRENT_REPORT','reason':'Independent attempt to discard an unsupported quantity','evidence':[{'kind':r['kind'],'source_index':r['source_index']}]}for r in q['required_candidate_assessments']if r['unit_id']==row['unit_id']]
  try:outcome=acceptance(s,q,response);outcomes.append({'status':outcome['evidence_status']})
  except ValueError as e:outcomes.append({'status':'REJECTED','reason':str(e)})
 program=quantity_contract(units=s['units'],period={'fiscal_year':2025},scope=s['quantity_scope_context'])
 assert all(o['status']=='PASS'for o in outcomes)==expect,(name,outcomes)
 rows.append({'case':name,'parsed_native_coverage':coverage,'source_unit_count':len(s['units']),'program_native_nonphysical_roles':len(program['verified_nonphysical_native_roles']),'implementation_unresolved':program['implementation_unresolved'],'outcomes':outcomes})
Path(__file__).with_name('native-result.json').write_text(json.dumps({'rows':rows,'new_calls':[0,0,0],'evidence_type':'SYNTHETIC_ORIGINAL_HTML_NATIVE_PARSE_TO_ACCEPTANCE'},indent=2)+'\n');print(json.dumps(rows,indent=2))

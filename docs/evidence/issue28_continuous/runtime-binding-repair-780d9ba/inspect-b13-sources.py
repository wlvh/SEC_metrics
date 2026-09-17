from pathlib import Path
import json,re,socket,sys
from unittest.mock import patch
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(R/'scripts'))
from vnext.normal_annual_input import prepare_saved_annual_input
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import verify_saved_source_proofs
from vnext.text_coverage import build_text_document
from vnext.deterministic_router import parse_accession_xbrl_source
company=sys.argv[1];out=Path(sys.argv[2]);assert not out.exists()
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch('sec_http.urlopen',side_effect=AssertionError('NO_SEC')):
 a=prepare_saved_annual_input(repo_root=R,company_id=company)
 reader=_Sources(R,company,a['entity']);original=reader.primary(a['filing'])
 auth=verify_saved_source_proofs(data_root=R,proofs=a['source_proofs'])
 d=build_text_document(raw_bytes=original['raw_bytes'],raw_blob=original['raw_blob'],source_reference=original['source_reference'],expected_company_id=company,expected_cik=a['entity'],expected_period_end=a['filing']['reportDate'])
 matches=[]
 for b in d['blocks']:
  if re.search(r'\b(?:capacity|utilization|production|produced|manufacturing)\b',b['text'],re.I):
   matches.append({k:b[k] for k in ['block_index','text','raw_start_byte','raw_end_byte','raw_span_sha256']})
 native=parse_accession_xbrl_source(raw_bytes=original['raw_bytes'])
 facts=[dict(f) for f in native.facts if re.search(r'capacity|utiliz|produc|manufactur',f['concept'],re.I)]
 result={'company_id':company,'annual':a,'source_reference':original['source_reference'],'raw_blob':original['raw_blob'],'source_authority':auth,'block_count':len(d['blocks']),'matched_blocks':matches,'native_candidates':facts,'amendments':a['amendments'],'status':'READ_ONLY_SOURCE_INSPECTION_NOT_A_B13_RESULT','calls':{'provider':0,'paid':0,'sec':0}}
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(company,len(matches),'blocks',len(facts),'native candidates')

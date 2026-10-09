import json,sys,hashlib
from pathlib import Path
ROOT=Path('/Users/lyuhongwang/Developer/SEC_metrics');sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from tests.vnext.test_text_coverage import annual
from tests.vnext.test_text_business_candidates import BODY,source_arguments
from vnext.regulatory_investigation_candidates import prepare_regulatory_investigation_candidates as prepare
OUT=Path(__file__).parent
if (OUT/'index.json').exists():raise SystemExit('Preserve first evidence; choose a new directory')
cases={
 'actual_current_control':'We are cooperating with the DOJ inquiry.',
 'private_background_control':'We received a subpoena from a private plaintiff in a contract lawsuit discussing SEC investigations.',
 'conditional_same_sentence_control':'We are cooperating with the DOJ inquiry if one is opened.',
 'historical_quoted_paragraph':'The following quotation is from our 2018 annual report; the inquiry was closed in 2019.</p><blockquote><p>We are cooperating with the DOJ inquiry.</p></blockquote><p>This is a historical quotation.',
 'third_party_quoted_paragraph':'Our supplier Delta provided this statement about its own investigation:</p><blockquote><p>We are cooperating with the DOJ inquiry.</p></blockquote><p>Delta is not affiliated with the registrant.',
 'conditional_quoted_paragraph':'If the DOJ were to open an inquiry, our hypothetical response would be:</p><blockquote><p>We are cooperating with the DOJ inquiry.</p></blockquote><p>No such inquiry has been opened.',
 'adjacent_closed_status':'We are cooperating with the DOJ inquiry.</p><p>This inquiry was closed in January 2021.',
 'sec_reports_private_actor':'The SEC reported that private plaintiff Delta issued a subpoena to Example Incorporated in a contract dispute.',
 'sec_denies_action':'The SEC denied that it issued a subpoena to Example Incorporated.',
 'government_private_insurer':'We received a subpoena from Government Employees Insurance Company, a private insurer, in its contract lawsuit.',
 'conference_background':'We are cooperating with the SEC on its conference about enforcement practices.'
}
paths=['scripts/vnext/regulatory_investigation_candidates.py','catalog/r6/regulatory_investigation_candidates_v1.json','tests/vnext/test_regulatory_investigation_candidates.py']
(OUT/'code-hashes.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},indent=2))
rows=[]
for name,text in cases.items():
 raw=annual(BODY.replace('If a regulator conducts an investigation, our expenses could increase.',text)).replace(b'</ix:hidden>',b'<ix:nonNumeric name="dei:EntityRegistrantName" contextRef="annual">Example Incorporated</ix:nonNumeric></ix:hidden>')
 a=source_arguments(raw);p=prepare(**a)
 (OUT/(name+'.html')).write_bytes(raw);(OUT/(name+'.bundle.json')).write_text(json.dumps(p,ensure_ascii=False,indent=2))
 facts=[{**f,'excerpt':c['excerpt'],'context_excerpts':c['context_excerpts'],'requires_semantic_review':c['requires_semantic_review']} for c in p['candidates'] for f in c['facts']]
 row={'case':name,'source_sha256':hashlib.sha256(raw).hexdigest(),'supported_fact_count':p['supported_fact_count'],'facts':facts,'native_result_created':p['native_result_created'],'semantic_scope_completeness_asserted':p['semantic_scope_completeness_asserted']};rows.append(row)
 print(name,p['supported_fact_count'],[(f['rule_id'],f['status'],f['current_status_asserted'],f['authority_to_action_relation_proven']) for f in facts],flush=True)
(OUT/'index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))

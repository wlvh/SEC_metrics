"""Read-only, bounded remaining-source evidence; no ratio or absence approval."""
from pathlib import Path
import json,hashlib
from vnext.deterministic_router import parse_accession_xbrl_source
root=Path(__file__).resolve().parents[4];out=Path(__file__).with_name('bounded-remaining-source-audit.json')
selections=[('pfizer','evidence/request_attempts/17/175e07c21ee258eddd9952e443d34df2a297d0c38e2d1312dff0a64a31c401ab/pfe-20251231.htm',[2861,2869]),('jpmorgan_chase','evidence/request_attempts/4d/4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/jpm-20251231.htm',[6580,6582])]
rows=[]
for company,name,ordinals in selections:
 p=root/name;raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==p.parent.name
 parsed=parse_accession_xbrl_source(raw_bytes=raw);facts=[f for f in parsed.facts if f['ordinal'] in ordinals];assert len(facts)==len(ordinals)
 rows.append({'company_id':company,'original_path':name,'original_sha256':p.parent.name,'scope':'Selected original lessee policy and operating lease table, not a whole-report absence proof','facts':[{'ordinal':f['ordinal'],'qualified_name':f['qualified_name'],'text':f['text']} for f in facts],'supported_observation':'JPM explicitly says predominantly operating leases; operating lease table is not a complete finance-lease balance.' if company=='jpmorgan_chase' else 'The liability table explicitly applies to operating leases. It cannot supply finance-lease liabilities or establish zero.','B06_ratio_created':False})
spec=root/'catalog/r5/C04_auditor_changes_v2.md';text=spec.read_text();rule=json.loads(text.split('---')[1])['quality_rule']
report={'record_type':'BOUNDED_REMAINING_SOURCE_AUDIT','lease_rows':rows,'C04':{'spec_path':str(spec.relative_to(root)),'spec_sha256':hashlib.sha256(spec.read_bytes()).hexdigest(),'current_absence_rule':rule['absence'],'accepted_event_forms':rule['event_forms'],'current_paramount_evidence':'docs/evidence/issue28_continuous/paramount-c04-source-inspection/registration-variants-real-material/source-analysis.json','unresolved_decision':'Using explicit Item9/continuous-auditor prose instead of same-registrant prior AuditorName requires a successor acceptance-rule decision. No value0 or cross-CIK combination is granted by this audit.'},'source_updated_or_requested':False,'new_calls':[0,0,0],'new_complete_coordinates':0,'limits':'This audit narrows why the shortcuts are unsupported. It does not certify full SEC nondisclosure, complete B06 debt, C04 value, or all390 acceptance.'}
out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({'status':'BOUNDED_ORIGINAL_FACTS_VERIFIED','new_calls':[0,0,0],'new_complete_coordinates':0})

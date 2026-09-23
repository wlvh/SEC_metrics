"""Use already saved originals to narrow B06/C04 obligations; no new values."""
from pathlib import Path
import json,re,hashlib,tarfile
from vnext.r6_semantic_review import _source_items
from vnext.normal_source_authority import ROOT
out=Path(__file__).resolve().parent
source_path=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/calls/0171/source.json');source=json.loads(source_path.read_text());equity=[]
for unit in source['units']:
 kind,items=_source_items(unit)
 if kind!='NATIVE_FACT':continue
 for ordinal,fact in items.items():
  if re.search('equity|stockholders',fact.get('qualified_name',''),re.I) is None:continue
  context=unit['payload']['contexts'].get(fact.get('context_ref'),{}).get('raw_xml','')
  equity.append({'ordinal':ordinal,'name':fact['qualified_name'],'text':fact['text'],'unit_ref':fact.get('unit_ref'),'scale':fact.get('scale'),'sign':fact.get('sign'),'context_ref':fact.get('context_ref'),'context_xml':context,'instant':re.findall(r'<[^>]*:instant>(.*?)</[^>]*:instant>',context),'dimensions':re.findall(r'<[^>]*:explicitMember\s+dimension="([^"]+)"[^>]*>(.*?)</[^>]*:explicitMember>',context)})
parent=[f for f in equity if f['name']=='us-gaap:StockholdersEquity' and f['instant']==['2025-12-31']]
assert len(parent)==1 and not parent[0]['dimensions']
package=ROOT/'docs/evidence/issue28_continuous/paramount-c04-source-inspection/registration-variants-real-material';index=json.loads((package/'material-index.json').read_text());analysis=json.loads((package/'source-analysis.json').read_text());archive=package/index['archive'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==index['archive_binding']['sha256'];raws={}
with tarfile.open(archive) as tf:
 for row in analysis['source_files']:
  sha=row['raw_sha256'];name='objects/'+sha
  if name in index['objects']:
   raw=tf.extractfile(name).read();assert hashlib.sha256(raw).hexdigest()==sha;raws[row['ordinal']]=raw
 for anchor in analysis['anchors']:
  raw=raws[anchor['ordinal']];assert hashlib.sha256(raw[anchor['raw_start_byte']:anchor['raw_end_byte']]).hexdigest()==anchor['raw_span_sha256']
spec=json.loads((ROOT/'catalog/r5/C04_auditor_changes_v2.md').read_text().split('---')[1]);rule=spec['quality_rule']
report={'status':'OFFLINE_SOURCE_ELIGIBILITY_AND_POLICY_DEPENDENCIES','new_calls':[0,0,0],'Ford_B06':{'saved_source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'native_equity_fact_count':len(equity),'current_parent_equity_facts':parent,'inventory':'ford-equity-native-inventory.json','conclusion':'Current parent StockholdersEquity fact has no segment dimension: consolidated, not an independently established industrial denominator. Component/NCI/credit equity must not be subtracted without a proven scope/elimination relationship. This tagged-fact census does not prove whole-report nondisclosure.','new_ratio':None},'Paramount_C04':{'archive_read_only':True,'verified_original_anchors':len(analysis['anchors']),'current_absence_rule':rule['absence'],'current_event_forms':rule['event_forms'],'source_facts':analysis['factual_conclusions'],'policy_decision_needed':'If a successor no-change branch is desired for a new registrant lacking a same-CIK prior annual AuditorName, explicitly define the acceptable first-period audit-history evidence and event coverage; currentv2 has no such negative branch. Do not cross CIKs, treat EY subsidiary consent or PwC employment as issuer change, or replace missing comparison with Item9 None.','new_metric_value':None},'other_B06':'Pfizer/JPM operating-lease evidence and Southwest supplier-credit relationship remain limited; unchanged original investigations reused, no zero-finance-lease inference or business-definition relaxation.','complete_390_credit':False,'formal_retirement_or_adoption':False}
(out/'ford-equity-native-inventory.json').write_text(json.dumps(equity,ensure_ascii=False,indent=2)+'\n');(out/'provider-free-dependencies.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({'Ford_equity_facts':len(equity),'Ford_current_consolidated_parent_equity':parent,'C04_verified_anchors':len(analysis['anchors']),'new_calls':[0,0,0]})

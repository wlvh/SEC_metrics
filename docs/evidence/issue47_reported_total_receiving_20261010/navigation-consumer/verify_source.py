"""Recheck the same historical source, not the already correct company amount."""
import hashlib,json,subprocess,time
from pathlib import Path
from unittest.mock import patch
from vnext.normal_governance_input import _Sources
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.historical_dei import annual_period
from vnext.xbrl_namespace_policy import YEAR_OR_DATE_RELEASE
from tests.vnext.test_selected_revenue_scope_v1 import originals,APPROVED

old=Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/fiscal-range-salesforce-20261010/state/updates/B01/periods/FY2026/results/9e5d4bbd9c5343908ebd147475a2a251')
before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old.iterdir() if p.is_file()}
assessment=json.loads((old/'input-assessments.json').read_text())['assessments']['historical_statement']['selected_revenue_scope']
annual=assessment['annual_input']
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
reader=_Sources(source,'salesforce',annual['entity']);original=reader.auditor_filing(annual['filing'])
primary=next(x for x in original if x['raw_blob']['media_type']=='text/html')
xml=next(x for x in original if x['raw_blob']['media_type']=='application/xml')
reference=json.loads(subprocess.check_output(['git','show','5f9d6a76:docs/evidence/issue47_selected_label_20261010/actual-originals.json']))
label=next(s['resolution'] for s in reference['scenes'] if s['company_id']=='salesforce')
start=time.monotonic()
with patch('socket.socket.connect',side_effect=AssertionError('No HTTP')),patch('vnext.calculator.calculate_metric',side_effect=AssertionError('No financial calculation')):
    scope=reported_revenue_scope(primary=primary,xml=xml,annual=annual,approved_concepts=assessment['approved_concepts'],
        namespace_policy=YEAR_OR_DATE_RELEASE,annual_period_reader=annual_period,fiscal_label_resolution=label)
elapsed=time.monotonic()-start
assert scope['complete_scope_proven'] and scope['selected_fiscal_column_year']==2026
assert {(r['total']['value'],r['total']['period_start'],r['total']['period_end'],r['xml_check'])
        for r in scope['reported_totals']}=={('41525000000','2025-02-01','2026-01-31','MATCH')}
assert annual['table_input']['target_period']['fiscal_year']==2025
assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in old.iterdir() if p.is_file()}

# Constructed source controls keep the same API's rejection boundary explicit.
fixture,_,sample_annual=originals()
controls=[]
for name,text in [('unknown_subject','<div>Only Subsidiary Beta is included.</div>'),
                  ('recognized_navigation','<div>See accompanying Notes.</div><div>57</div><div>Table of Contents</div>')]:
    raw=fixture['raw_bytes'].replace(b'<div>Consolidated Statements of Income</div>',
        text.encode()+b'<div>Consolidated Statements of Income</div>')
    changed={**fixture,'raw_bytes':raw,'source_reference':{**fixture['source_reference'],
        'raw_asset_id':'sha256:'+hashlib.sha256(raw).hexdigest()}}
    try:checked=reported_revenue_scope(primary=changed,annual=sample_annual,approved_concepts=APPROVED)
    except ValueError as e:
        assert name=='unknown_subject' and 'STATEMENT_HEADING_SCOPE_UNRESOLVED' in str(e)
        controls.append({'constructed_case':name,'reason':str(e),'refused':True})
    else:
        assert name=='recognized_navigation' and checked['complete_scope_proven']
        nav=checked['reported_totals'][0]['statement_scope']['preceding_navigation_sources']
        assert [b['visible_text'] for b in nav]==['See accompanying Notes.','57','Table of Contents']
        controls.append({'constructed_case':name,'navigation_source_spans':nav,'refused':False})
record={'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'seconds':elapsed,
        'scope':scope,'raw_dei_fiscal_year':2025,'resolved_issuer_fiscal_year':2026,
        'old_saved_result_files_preserved':before,'original_result_not_recomputed':True,
        'constructed_controls_not_financial_acceptance':controls,'new_calls':[0,0,0]}
Path('work/reported-navigation-consumer/final-source-probe.json').write_text(json.dumps(record,indent=2)+'\n')
print('Historical source:',elapsed,'total:',scope['reported_totals'][0]['total']['value'],
      'native dates preserved, raw FY2025/issuer FY2026; old files:',len(before))

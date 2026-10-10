from pathlib import Path
import json,hashlib,time
from vnext.historical_dei import annual_period
from vnext.selected_reported_revenue_v2 import reported_revenue_scope
from vnext.specs import compile_spec_file
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs/evidence/request_attempts/50/50ea8e3119bf4e07e0ee54e29e2f844289afc6197d584594e6f8ed4325282b29/m-20240203.htm')
start=time.monotonic();raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='50ea8e3119bf4e07e0ee54e29e2f844289afc6197d584594e6f8ed4325282b29'
filing={'accessionNumber':'0001628280-24-012734','primaryDocument':'m-20240203.htm','reportDate':'2024-02-03','form':'10-K','filingDate':'2024-03-20'}
period=annual_period(raw=raw,cik='794367',filing=filing)
annual={'company_id':'macys','entity':'794367','filing':filing,'table_input':{'target_period':period}}
primary={'raw_bytes':raw,'source_reference':{'company_id':'macys','accession':filing['accessionNumber'],'raw_asset_id':'sha256:'+sha,'source_url':'https://www.sec.gov/Archives/edgar/data/794367/000162828024012734/m-20240203.htm'}}
spec=compile_spec_file(path=Path('catalog/metrics/B01_revenue.md'),dependency_specs={})
concepts=spec['compiled']['inputs']['revenue']['structured_role']['approved_concepts']
scope=reported_revenue_scope(primary=primary,annual=annual,approved_concepts=concepts,annual_period_reader=annual_period)
assert len(scope['reported_totals'])==1
assert scope['reported_totals'][0]['total']['value']=='23866000000'
assert period=={'fiscal_year':2023,'period_start':'2023-01-29','period_end':'2024-02-03'}
Path('docs/evidence/issue28_reported_revenue_20261010/actual-source-final.json').write_text(json.dumps({'source_path':str(source),'source_sha256':sha,'scope':scope,'seconds':time.monotonic()-start,'stage':'SOURCE_PROTOTYPE_NOT_CALCULATOR_OR_COMPANY_ENTRY','calls':[0,0,0]},indent=2)+'\n')
print(scope['status'],scope['reported_totals'][0]['total']['value'],period,time.monotonic()-start)

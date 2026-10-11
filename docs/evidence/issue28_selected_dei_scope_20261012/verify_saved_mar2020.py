"""Exact existing Mar2020 originals, explicit source policy; no new calls/value."""
from pathlib import Path
import json,socket,hashlib,time
from unittest.mock import patch
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_period_selection import resolve_period_selection
from vnext.normal_governance_input import _Sources
from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.annual_amendment_scope import _source
from vnext.text_coverage import build_text_document,verify_text_document
from vnext.instant_balance_amendment import _correction_flag
from vnext.xbrl_namespace_policy import YEAR_QUARTER_OR_DATE
source=Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs');company='marriott_international';e=Path(__file__).parent;started=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 selection=resolve_period_selection(repo_root=source,company_id=company,fiscal_year=2020)
 prepared=prepare_historical_annual_input(repo_root=source,company_id=company,period_selection=selection)
 reader=_Sources(source,company,prepared['entity']);original=reader.primary(prepared['filing']);results=[]
 def entry(item,filing):return {'raw':item['raw_bytes'],'blob':item['raw_blob'],'reference':item['source_reference'],'filing':filing}
 for filing in prepared['amendments']:
  amended=reader.primary(filing);args=dict(original=entry(original,prepared['filing']),amendment=entry(amended,filing),company_id=company,cik=prepared['entity'],note_layout='inline-paragraphs-v2')
  try:inspect_annual_amendment_scope(**args);before='UNEXPECTED_DEFAULT_ADMISSION'
  except ValueError as error:before=str(error)
  resolved=[]
  for item,filing_identity in ((original,prepared['filing']),(amended,filing)):
   identity=_source(**entry(item,filing_identity),company_id=company,cik=prepared['entity'],period_end=prepared['filing']['reportDate'],namespace_policy=YEAR_QUARTER_OR_DATE)
   docargs=dict(raw_bytes=item['raw_bytes'],raw_blob=item['raw_blob'],source_reference=item['source_reference'],expected_company_id=company,expected_cik=prepared['entity'],expected_period_end=prepared['filing']['reportDate'],namespace_policy=YEAR_QUARTER_OR_DATE)
   assert verify_text_document(document=identity['document'],**docargs)==identity['document']
   resolved.append(identity)
  scope=None;refusal=None
  try:scope=inspect_annual_amendment_scope(**args,namespace_policy=YEAR_QUARTER_OR_DATE)
  except ValueError as error:refusal={'reason':str(error),'error_type':type(error).__name__}
  assert refusal and refusal['reason']=='AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED',refusal
  original_source,amended_source=resolved
  try:flag=_correction_flag(amended['raw_bytes'],{'amendment':amended_source},namespace_policy=YEAR_QUARTER_OR_DATE);flag_state={'status':'FOUND','flag':flag['fact']['text']}
  except ValueError as error:flag_state={'status':'NOT_PROVEN','reason':str(error)}
  row={'original':original['source_reference'],'amendment':amended['source_reference'],'default_error':before,'explicit_source_identity_passed':True,'annual_scope_refusal':refusal,'original_period':original_source['period'],'amended_period':amended_source['period'],'raw_amendment_flags':amended_source['raw_amendment_flag_values'],'income_statement_admission_proven':False,'correction_flag_observation':flag_state,'explicit_namespace_policy':YEAR_QUARTER_OR_DATE,'exact_document_replay':True,'text_document_ids':[x['document']['text_document_id'] for x in resolved]};results.append(row)
  print('EXPLICIT_SOURCE_IDENTITY_AND_REPLAY_PASS_WITH_NAMED_SCOPE_HOLD',refusal,flag_state,flush=True)
 report={'program_root':str(Path.cwd()),'source_root':str(source),'seconds':time.perf_counter()-started,'working_source_files_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('scripts/vnext/text_coverage.py'),Path('scripts/vnext/annual_amendment_scope.py'),Path('scripts/vnext/annual_amendment_scope_v2.py'),Path('scripts/vnext/instant_balance_amendment.py'),Path('scripts/vnext/instant_balance_amendment_v2.py')]},'checks':results,'new_calls':[0,0,0],'metric_result_created':False}
 (e/'actual-saved-scope.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS_EXACT_ORIGINAL_SOURCE_SCOPE_AND_REPLAY',report['seconds'],[(r['explicit_source_identity_passed'],r['annual_scope_refusal'],r['correction_flag_observation']) for r in results],flush=True)

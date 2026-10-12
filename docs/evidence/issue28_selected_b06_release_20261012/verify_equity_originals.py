"""Selected saved originals at the public denominator source boundary."""
import argparse,json,socket,time
from pathlib import Path
from unittest.mock import patch
from vnext.historical_b06_case import prepare_selected_debt_sources
from vnext.ordinary_debt_guard import prepare_current_guarded_b06_result
from vnext.b06_guarded_result_v3 import _source_equity
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for company,year in [('enphase_energy',2021),('salesforce',2022)]:
  start=time.perf_counter();selected=prepare_selected_debt_sources(repo_root=a.source_root,company_id=company,fiscal_year=year)
  original=selected['annual']['original_input'];preparation=selected['preparation'];period=original['table_input']['target_period']
  target={'entity':original['entity'],'period_end':period['period_end']}
  try:_source_equity(raw=preparation['primary']['raw_bytes'],kind='primary_inline',target=target,period=period,filing=original['filing'])
  except ValueError as error:old_error={'type':type(error).__name__,'reason':str(error)}
  else:raise AssertionError('Year-only default unexpectedly accepted the quarterly declaration')
  result=prepare_current_guarded_b06_result(repo_root=a.source_root,company_id=company,rules_root=Path.cwd(),preparation=preparation,dei_release='YEAR_QUARTER_OR_DATE',namespace_policy='YEAR_OR_DATE_RELEASE')
  assert result['status']=='CONTINUE_DEBT_PATH' and result['result'] is None and result['debt_completeness']=='NOT_EVALUATED'
  assert result['source_reader_options']=={'dei_release':'YEAR_QUARTER_OR_DATE','namespace_policy':'YEAR_OR_DATE_RELEASE'}
  rows.append({'company':company,'year':year,'filing':original['filing'],'actual_period':period,'primary':preparation['primary']['source_reference'],'xml':preparation['xml']['source_reference'],'before':old_error,'guard_status':result['status'],'equity_proof':result['equity_proof'],'reader_options':result['source_reader_options'],'seconds':time.perf_counter()-start,'full_debt_scope_proven':False,'financial_result_created':False,'new_calls':[0,0,0]})
a.output.write_text(json.dumps({'rows':rows,'code_root':str(Path.cwd()),'source_root':str(a.source_root),'scope':'Public denominator original-source proof only; not full B06/company acceptance'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'company':x['company'],'status':x['guard_status'],'equity':x['equity_proof']['value'],'seconds':x['seconds'],'full_B06':False} for x in rows]))

"""Use real selected originals and amendment packet at the shared B06 seam."""
import argparse, json, socket, time, traceback
from pathlib import Path
from unittest.mock import patch
from vnext.historical_b06_case import prepare_selected_debt_sources, prepare_selected_debt_input
from vnext.current_b06_case import prepare_selected_b06_case
from vnext.normal_annual_input_v2 import exact_json_value

p=argparse.ArgumentParser()
p.add_argument('--source-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
rows=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 for company,year in [('enphase_energy',2021),('salesforce',2022)]:
  start=time.perf_counter()
  selected=prepare_selected_debt_sources(repo_root=a.source_root,company_id=company,fiscal_year=year)
  packet=prepare_selected_debt_input(repo_root=a.source_root,selected=selected)
  row={'company':company,'year':year,'input_decision':packet['decision'],
       'primary':selected['preparation']['primary']['source_reference'],
       'filing':selected['annual']['filing'],'new_calls':[0,0,0]}
  try:
   case=prepare_selected_b06_case(source_root=a.source_root,company_id=company,
       preparation=selected['preparation'],annual=selected['annual'],packet=packet,
       dei_release='YEAR_QUARTER_OR_DATE',namespace_policy='YEAR_OR_DATE_RELEASE')
   row.update(result=case['results']['B06'],selection=case['selection'],
       input_assessments=case['input_assessments'],source_reader_options=case['input_binding']['source_reader_options'])
  except Exception as error:
   row['failure']={'type':type(error).__name__,'reason':str(error),'traceback':traceback.format_exc()}
  row['seconds']=str(time.perf_counter()-start)
  rows.append(row)
  a.output.write_text(json.dumps(exact_json_value({'rows':rows,'code_root':str(Path.cwd()),
      'source_root':str(a.source_root),'scope':'Selected public B06 source/case, not company writer/read acceptance'}),ensure_ascii=False,indent=2)+'\n')
  print(json.dumps({k:row[k] for k in ['company','year','seconds','failure'] if k in row}
      | {'result':row.get('result',{})}),flush=True)
assert all('failure' not in row for row in rows), 'A public selected route still failed'

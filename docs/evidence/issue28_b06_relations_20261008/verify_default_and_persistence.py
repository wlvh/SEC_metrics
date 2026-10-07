from pathlib import Path
import json,subprocess,sys,types,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.ordinary_special_debt_scope import prepare_special_debt_case
from vnext.canonical import content_hash,atomic_write_json,strict_json_file
import argparse
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);src=p.parse_args().source_root.resolve()
old=types.ModuleType('vnext._baseline_debt');old.__package__='vnext'
exec(subprocess.check_output(['git','show','8588ccbbb1c91d81e0fb1a89dff3575214282549:scripts/vnext/ordinary_special_debt_scope.py'],cwd=ROOT),old.__dict__)
start=time.monotonic();a=old.prepare_special_debt_case(repo_root=src,company_id='ford_motor_company')
b=prepare_special_debt_case(repo_root=src,company_id='ford_motor_company')
assert a==b
c=prepare_special_debt_case(repo_root=src,company_id='ford_motor_company',reported_relations=True)
p=Path('/private/tmp/issue28-b06-v2-source-case.json');atomic_write_json(path=p,value=c)
loaded=strict_json_file(path=p)
assert loaded==c
x=loaded['input_binding']['scope_source'];assert x['lease_inclusion']['status']=='REPORTED_INCLUDED'
assert x['lease_inclusion']['component_total']=='890000000'
assert x['lease_inclusion']['additional_debt_amount']=='0'
assert x['reported_subtotal']=='21919000000' and x['definition_complete'] is False
assert loaded['results']['B06']['value'] is None
print(json.dumps({'baseline_sha':'8588ccbbb1c91d81e0fb1a89dff3575214282549','seconds':time.monotonic()-start,
'default_case_identical_to_main':True,'default_case_id':content_hash(value=a),
'selected_case_id':content_hash(value=c),'saved_read_identical':True,
'saved_bytes':p.stat().st_size,'record_type':x['record_type'],'lease_additional_amount':x['lease_inclusion']['additional_debt_amount'],
'B06_publication':loaded['results']['B06']['publication'],'B06_value':loaded['results']['B06']['value'],
'new_calls':[0,0,0],'native_run_created':False},indent=2))

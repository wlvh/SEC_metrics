"""Exercise the actual source preparation API; no Run or external requests."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.ordinary_special_debt_scope import prepare_special_debt_case
from vnext.ordinary_reported_lease_scope import prepare_reported_lease_case
from vnext.canonical import sha256_file

p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True)
a=p.parse_args();start=time.monotonic()
c=prepare_reported_lease_case(repo_root=a.source_root,company_id='ford_motor_company')
s=c['selection']['scope_source'];r=c['results']['B06']
assert s['reported_subtotal']=='21919000000'
assert s['lease_inclusion']['status']=='REPORTED_INCLUDED'
assert s['lease_inclusion']['component_total']=='890000000'
assert s['lease_inclusion']['additional_debt_amount']=='0'
assert s['definition_complete'] is False and s['ratio'] is None
assert r['publication']=='WITHHELD' and r['value'] is None
print(json.dumps({'seconds':time.monotonic()-start,'code_root':str(ROOT),
 'source_root':str(a.source_root.resolve()),'record_type':s['record_type'],
 'accession':s['accession'],'period_end':s['period_end'],'reported_subtotal':s['reported_subtotal'],
 'lease_inclusion':s['lease_inclusion'],'limitations':s['limitations'],
 'result':{'result_id':r['result_id'],'publication':r['publication'],'value':r['value']},
 'processing_files':{q:sha256_file(path=ROOT/q) for q in (
  'scripts/vnext/industrial_lease_relation.py','scripts/vnext/ordinary_special_debt_scope.py')},
 'new_calls':{'provider':0,'paid':0,'sec':0},'native_run_created':False},ensure_ascii=False,indent=2))

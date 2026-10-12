import json
from copy import deepcopy
from vnext.normal_history_catalog import block_last_days,history_block_coherence
from vnext.c04_registration_successor import _checked_inventory_rows
name='CIK0000012345-submissions-001.json';shard={'name':name,'filingFrom':'2021-01-01','filingTo':'2022-12-30','filingCount':1};index={'filings':{'recent':{'filingDate':['2023-01-02']}}};body={'form':['8-K12B'],'reportDate':['2022-12-31'],'filingDate':['2022-12-31'],'accessionNumber':['0000012345-22-000007'],'primaryDocument':['event.htm']}
last=block_last_days(payload=index,shards=[shard])[name];assert last=='2023-01-01'
try:_checked_inventory_rows(body,inventory_name=name,shard=shard)
except ValueError as e:assert str(e)=='C04_REGISTRATION_HISTORY_BODY_ALIGNMENT_CONFLICT'
else:raise AssertionError('Default old bound changed')
rows=_checked_inventory_rows(body,inventory_name=name,shard=shard,block_last_day=last);assert rows[0]['form']=='8-K12B' and rows[0]['filingDate']=='2022-12-31'
negatives=[]
for changed,meta in [(dict(body,filingDate=['2023-01-02']),shard),(body,dict(shard,filingCount=2))]:
 try:_checked_inventory_rows(changed,inventory_name=name,shard=meta,block_last_day=last)
 except ValueError as e:negatives.append(str(e));assert str(e)=='C04_REGISTRATION_HISTORY_BODY_ALIGNMENT_CONFLICT'
 else:raise AssertionError('Wrong bound/count admitted')
print(json.dumps({'constructed_control':True,'fixed_public_core':'a1bafae4','gap_day_row':rows[0],'derived_last_day':last,'default_old_refusal_preserved':True,'beyond_bound_and_count_refusals':negatives,'new_calls':[0,0,0]},indent=2))

import json
from vnext.normal_history_catalog import block_last_days,history_block_coherence
from vnext.c04_registration_successor import _checked_inventory_rows
name='CIK0000012345-submissions-001.json'
shard={'name':name,'filingFrom':'2021-01-01','filingTo':'2022-12-30','filingCount':1}
index={'filings':{'recent':{'filingDate':['2023-01-02']}}}
body={'form':['8-K12B'],'reportDate':['2022-12-31'],'filingDate':['2022-12-31'],
'accessionNumber':['0000012345-22-000007'],'primaryDocument':['event.htm']}
rows=[{k:v[0] for k,v in body.items()}]
last=block_last_days(payload=index,shards=[shard])[name]
assert last=='2023-01-01'
assert history_block_coherence(shard=shard,body=body,rows=rows,last_day=last) is None
try:_checked_inventory_rows(body,inventory_name=name,shard=shard)
except ValueError as e:
 assert str(e)=='C04_REGISTRATION_HISTORY_BODY_ALIGNMENT_CONFLICT'
 print(json.dumps({'constructed_control':True,'selector_accepts':True,'derived_last_day':last,'public_reread_refuses':str(e),'row':rows[0],'shard':shard,'new_calls':[0,0,0]},indent=2))
else:raise AssertionError('Expected the reported public reread refusal')

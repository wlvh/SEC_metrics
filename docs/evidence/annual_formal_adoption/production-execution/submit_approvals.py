import sys,json,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path(__file__).resolve().parent
sys.path[:0]=[str(R),str(R/'scripts')]
from vnext import annual_candidate,annual_publication_authority as auth
assert json.loads((O/'preflight.json').read_text())['status']=='PASSED_FIXED_PLAN_COMPLETE_PACKAGE_AND_R3_PREDECESSOR'
assert subprocess.check_output(['gh','api','user','--jq','.login'],text=True).strip()=='wlvh'
plan=json.loads((R/'docs/evidence/annual_formal_adoption/final/pending-production-plan.json').read_text()); template=json.loads((R/'docs/evidence/annual_formal_adoption/final/approval-templates.json').read_text())
pull=annual_candidate._github('repos/wlvh/SEC_metrics/pulls/40')
assert pull['head']['sha']=='36a91de058ac2fe6aee660a090f2b14d8527deb7' and pull['merged'] is False
comments=[]; page=1
while True:
 values=annual_candidate._github('repos/wlvh/SEC_metrics/issues/40/comments?per_page=100&page='+str(page));comments.extend(values)
 if len(values)<100:break
 page+=1
(O/'pr40-comments-before-approval.json').write_text(json.dumps(comments,ensure_ascii=False,indent=2)+'\n')
def post(body,label):
 path=O/(label+'-request.json'); assert not path.exists()
 path.write_text(json.dumps({'body':body},ensure_ascii=False)+'\n')
 raw=subprocess.check_output(['gh','api','--method','POST','repos/wlvh/SEC_metrics/issues/40/comments','--input',str(path)],text=True)
 (O/(label+'-posted.json')).write_text(raw);return json.loads(raw)
result={}
for key in ['requirement_transition','publication_decision']:
 expected=template[key]; found=[]
 for c in comments:
  try:matches=json.loads(c['body'])==expected
  except (ValueError,TypeError):matches=False
  if matches:
   try:checked=auth._comment(plan,c['html_url'],expected)
   except ValueError:continue
   found.append(checked)
 assert len(found)<=1,'Multiple valid approvals require exact-state inspection'
 value=found[0] if found else post(json.dumps(expected,ensure_ascii=False,indent=2),key)
 result[key]=auth._comment(plan,value['html_url'],expected)
 with (O/'approval-progress.jsonl').open('a') as f:f.write(json.dumps({'key':key,'reused':bool(found),'verified':result[key]},ensure_ascii=False)+'\n')
body='这两条批准由 Codex 根据用户于 2026-09-10 在对话中的明确委托，通过已认证的 wlvh 账户代提交。批准仅对应本次列明的 PR40、固定计划、确切候选与完整包，业务调用预算为 0/0/0。它们不表示用户亲自在 GitHub 输入了评论，也不构成一次新的人工代码审查。\n\nRequirement transition：'+result['requirement_transition']['html_url']+'\n\nPublication decision：'+result['publication_decision']['html_url']+'\n\n固定计划：'+plan['plan_id']+'\n获审交付 head：36a91de058ac2fe6aee660a090f2b14d8527deb7\n受审 implementation head：'+plan['code']['exact_head']+'\n完整包：'+plan['binding']['publication_id']+'\n目标根：'+plan['target_root']+'\n预期前驱：'+plan['predecessor']['publication_id']+'\n\n本说明只公开委托代提交关系，不替代两条机器批准，不扩大固定计划的有限 publish/rollback/restore/recover 范围，不授予新增抽取、R4 重启或下一阶段权限。'
found=[c for c in comments if c['body']==body and c['user']['login']=='wlvh' and c['created_at']==c['updated_at']]
assert len(found)<=1
value=found[0] if found else post(body,'delegation-notice')
verified=annual_candidate._github('repos/wlvh/SEC_metrics/issues/comments/'+str(value['id']))
assert verified['body']==body and verified['user']['login']=='wlvh' and verified['created_at']==verified['updated_at']
result['delegation_notice']={k:verified[k] for k in ['id','html_url','issue_url','body','created_at','updated_at','user']}
result['delegation']={'source':'2026-09-10 explicit user instruction in Codex task 01a081bb-9220-7de3-a311-b481906b3146','executor':'Codex','authenticated_github_actor':'wlvh','user_personally_typed_comments':False,'new_human_code_review':False,'local_delegation_record_sha256':hashlib.sha256((O/'USER_DELEGATION.md').read_bytes()).hexdigest()}
assert not (O/'approvals.json').exists();(O/'approvals.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k]['html_url'] for k in ['requirement_transition','publication_decision','delegation_notice']}))

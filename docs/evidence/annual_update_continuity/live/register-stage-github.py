import sys,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
r=Path('/Users/lyuhongwang/Developer/SEC_metrics');w=Path('/Users/lyuhongwang/Documents/Codex/2026-09-10/annual-update-continuity');sys.path[:0]=[str(r),str(r/'scripts')]
from vnext import annual_continuity as c
from vnext.annual_candidate import _github
from vnext.canonical import strict_json_file,strict_json_loads,canonical_json_bytes
assert _github('user')['login']=='wlvh'
stage=strict_json_file(path=w/'live-logs/stage-proposal-02.json');c.validate_stage(stage,execution=True)
body=(w/'live-logs/stage-proposal-02.json').read_text().strip();assert len(body)<65536
existing=_github('repos/wlvh/SEC_metrics/issues/41/comments?per_page=100')
matching=[]
for comment in existing:
 try: candidate=strict_json_loads(text=comment['body'])
 except ValueError: continue
 if candidate==stage:
  c.validate_owner(stage,comment);matching.append(comment)
assert len(matching)<=1
if matching: raw=matching[0];created=False
else:
 raw=json.loads(subprocess.check_output(['gh','api','--method','POST','repos/wlvh/SEC_metrics/issues/41/comments','--input','-'],input=json.dumps({'body':body}).encode()));created=True
# Persist the real response before the independent native read-back.
with (w/'live-logs/owner-stage-comment-created.json').open('xb') as out:out.write(canonical_json_bytes(value=raw))
binding=c.verify_stage(approval_url=raw['html_url'])
with (w/'live-logs/real-stage-binding.json').open('xb') as out:out.write(canonical_json_bytes(value=binding))
text='本阶段批准由 Codex 依用户于2026-09-10在当前任务中的明确委托，通过已认证的 wlvh 账户代登记。它不是用户亲自在GitHub输入的评论，也不是新的人工代码审查。\n\n真实阶段批准：'+raw['html_url']+'\n受审实现：'+stage['reviewed_code']['exact_head']+'；规则：annual_candidate_adoption_v3 / issue_28_v8。仅限本次 Marriott B01/B10 隔离历史连续运行；两份输入共用这一阶段批准，不需逐候选批准。provider/paid 总额最多3/3（正常两次，另一次仅满足根因修复与回归、独立复核条件后使用）；SEC最多6；自动重试0；实际生产根发布0。现有完整材料齐全，预计SEC0。截止：'+stage['expires_at_utc']+'；交付或额度耗尽即关闭。固定预算登记、每次原始来源/请求/Run/完整包与精确前驱仍由程序验证，不能通过换目录、head或批准重置。'
explanation=json.loads(subprocess.check_output(['gh','api','--method','POST','repos/wlvh/SEC_metrics/issues/41/comments','--input','-'],input=json.dumps({'body':text}).encode()))
verified=_github('repos/wlvh/SEC_metrics/issues/comments/'+str(explanation['id']));assert verified['body']==text and verified['user']['login']=='wlvh' and verified['created_at']==verified['updated_at']
with (w/'live-logs/delegation-comment.json').open('xb') as out:out.write(canonical_json_bytes(value=verified))
result={'stage_id':stage['stage_id'],'approval_url':raw['html_url'],'delegation_url':verified['html_url'],'created_new_approval':created,'verified_via':'annual_candidate._github + annual_continuity.verify_stage','time':datetime.now(timezone.utc).isoformat(),'expires_at_utc':stage['expires_at_utc'],'code':stage['reviewed_code'],'registration_id':stage['budget_registration']['registration_id'],'new_business_calls':[0,0,0]}
with (w/'live-logs/stage-approval-receipt.json').open('xb') as out:out.write(canonical_json_bytes(value=result))
print(json.dumps(result))

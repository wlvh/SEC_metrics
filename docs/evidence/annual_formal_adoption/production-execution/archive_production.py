"""Archive only the approved production artifacts and new execution evidence."""
from pathlib import Path
import json,hashlib,shutil,subprocess,re
from datetime import datetime,timezone
R=Path('/Users/lyuhongwang/Developer/SEC_metrics');O=Path(__file__).resolve().parent
D=R/'docs/evidence/annual_formal_adoption/production-execution'
def read(p):return json.loads(p.read_text())
def proof(p):
 b=p.read_bytes();return {'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
def git(*a):return subprocess.check_output(['git',*a],cwd=R,text=True).strip()
assert git('branch','--show-current')=='main'
verification=read(O/'production-verification.json'); assert verification['status']=='VERIFIED_REAL_PRODUCTION_ADOPTION_AND_COMPLETE_COLD_READ'
plan=read(O.parent.parent/'attempt-02/pending-production-plan.json');merger=read(O/'merge-and-main-sync.json');approvals=read(O/'approvals.json')
assert git('rev-parse','HEAD')==merger['merge_commit']
assert not git('diff',merger['merge_commit'],'--','scripts','tools','config','catalog','requirements','tests')
assert not D.exists(), 'Keep existing archives; inspect before selecting another archive'
# Complete execution facts, including the first deploy refusal, are retained.
labels=['activate','deploy','deploy-02','publish','read'];commands=[]
for label in labels:
 e=read(O/(label+'-execution.json')); commands.append({**e,'combined_log':{'path':str(O/(label+'.log')),**proof(O/(label+'.log'))},'sandbox_profile':'production-write-whitelist.sb' if label=='deploy' else ('production-write-whitelist-v2.sb' if label in ['deploy-02','publish'] else 'readonly-output-write-scope'), 'interpretation':'FAILED_BEFORE_PERMISSION_OR_ACTION_RESERVATION' if label=='deploy' else 'COMPLETED'})
 assert e['exit_status']==(2 if label=='deploy' else 0)
record={'status':'REAL_CANDIDATE_SPECIFIC_FORMAL_ADOPTION_COMPLETE','recorded_at_utc':datetime.now(timezone.utc).isoformat(),'merge_commit':merger['merge_commit'],'pr40_head_preserved':'36a91de058ac2fe6aee660a090f2b14d8527deb7','implementation_head':plan['code']['exact_head'],'code_binding':plan['code'],'plan_id':plan['plan_id'],'publication_id':plan['binding']['publication_id'],'manifest_file_sha256':plan['binding']['manifest_sha256'],'predecessor':plan['predecessor'],'actual_active':verification['active'],'activation_receipt_id':read(O/'activate.json')['receipt_id'],'action_id':verification['action']['action_id'],'switch_receipt_id':verification['native_switch_receipt']['switch_receipt_id'],'permission_id':verification['native_switch_receipt']['annual_authority']['permission_id'],'approval_urls':{k:approvals[k]['html_url'] for k in ['requirement_transition','publication_decision','delegation_notice']},'commands':commands,'new_provider_paid_sec_calls':[0,0,0],'pr38_historical_calls':[2,2,0],'original_final_review_files_unchanged':True,'same_year_source_and_execution_version_adoption_only':True,'next_business_stage_started':False}
(O/'execution-summary.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
text=f'''# 正式采纳与发布执行记录 — 2026-09-10

已在原目录 main 完成固定 Marriott FY2025 B01/B10 候选的首次正式采纳，部署和一次 publish 后，独立只读新进程回读通过。**当前 active 为 `{plan['binding']['publication_id']}`，前驱仍完整保留为原 R3。** 2项采纳+238项继承，327行公开矩阵；没有主动执行生产 rollback/restore 或故障注入。

- PR40 merge M：`{merger['merge_commit']}`，第二父为获审交付 `36a91de058ac2fe6aee660a090f2b14d8527deb7`；PR40本地/远端分支保留该head。
- 受审实现：`{plan['code']['exact_head']}`；实现与测试身份见 execution-summary.json。归档只增加发布数据/证据，不改变 scripts/tools/config/catalog/requirements/tests。归档提交C的实际身份在最终交付和Issue28记录，不作自引用。
- 固定plan对象ID：`{plan['plan_id']}`。目标manifest文件字节SHA：`{plan['binding']['manifest_sha256']}`。
- 激活receipt对象ID：`{record['activation_receipt_id']}`；正式生效由真实批准、权限和原生切换收据证明，冻结规则/包内PENDING字段及历史final文件不改。

## 真实批准及委托关系

- [Requirement transition]({record['approval_urls']['requirement_transition']})
- [独立 publication decision]({record['approval_urls']['publication_decision']})
- [公开委托代提交说明]({record['approval_urls']['delegation_notice']})

由Codex根据用户2026-09-10明确委托，经实际认证的wlvh账户提交；不表示用户亲自在GitHub输入，也不是一次新人工代码审查。原文及真实作者/时间/位置回读在 approvals.json，执行委托范围见 USER_DELEGATION.md。所有模型/SEC凭据均从执行子进程剥离；业务socket拒绝。必要GitHub审批/PR/Issue网络操作实际发生。

## 验收与公开差异

`production-verification.json`逐项关联active、完整包、原生action/switch receipt和实际permission，确认14兼容副本一致、无pending intent、两项原始来源可读，未选坐标与B03未误选，历史包/候选/失败/冻结政策/stash/worktree未变。

矩阵完整字段差异只有B10 filed_date从2026-02-10变为空；B01仍有该日期。B10原本已空的fiscal_year/form仍空，不能算本次新删除。证据表B01来源路径、原始来源hash、引用文字和parser版本更新，B10来源路径更新。全部前后字段见 field-differences-approved-package.json 和 production-verification.json；数值未变，不手工回填日期。

## 真实失败与恢复边界

发布前采证工具三次失败均保留：/dev/null保护规则、空目录枚举及JSON键顺序比较，第四次完整核验通过。首次deploy被外部OS正则定长表达式拒绝在permission写入前，只有空目录创建，无permission、publish action或intent，R3未变。修正为等价精确长度路径表达式并在隔离目录验证允许/禁止路径后，同一plan/同一批准的deploy-02成功。没有更改政策、核心代码、包或计划，没有重发批准。首次deploy失败日志不改为成功。

只有一次publish且已完成；rollback/restore未使用，recover未调用。不把exit0、NO_PENDING或旧反例资料当成当前发布证明。完整命令、开始/结束、退出状态、日志hash和真实Github响应在 execution-summary.json 及各 execution 文件。

## 旧PR与最终边界

#31/#33均closed/unmerged且分支保留；#34继续open/Draft/unmerged。#33正文“未执行”是生成时快照，实际同一计划后续曾JPM通过、Citi失败，该轮2/2/0；关闭说明已纠正范围，原transition、授权与执行历史保留，不追认内容正确性、不重启R4。

本轮新增provider/paid/SEC=0/0/0；PR38历史累计仍2/2/0。只是同年度来源与执行版本的候选特定正式衔接；不是生产FY2024→FY2025更新、未见材料泛化、长期自动运行或39指标全量完成。下一步仍由Issue28跟踪正常新输入、持续许可/触发、剩余指标迁移及旧路径退出。本轮完成后停止。
'''
(O/'README.md').write_text(text)
D.mkdir()
# Only top-level durable records/helpers; sandbox sample files, temp data and directories are not published.
index={}
for f in sorted(O.iterdir()):
 if not f.is_file() or f.suffix not in {'.json','.jsonl','.md','.log','.py','.sb'}:continue
 assert not f.is_symlink();shutil.copyfile(f,D/f.name);assert proof(f)==proof(D/f.name);index[f.name]={'external_path':str(f),**proof(f)}
(D/'archive-file-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
package=R/'outputs/publications'/plan['binding']['publication_id']
paths=[str(p.relative_to(R)) for p in package.rglob('*') if p.is_file()]
paths+=list(read(O/'root-mirror-paths.json').values())+['outputs/active_publication.json',str(Path(verification['permission_file']['path']).relative_to(R)),'outputs/annual_publication_actions/'+plan['plan_id'][7:]+'-publish.json','outputs/publication_switch_receipts/'+record['switch_receipt_id'][7:]+'.json']
paths += [str(p.relative_to(R)) for p in D.rglob('*') if p.is_file()]
paths=sorted(set(paths));assert all((R/p).is_file() and not (R/p).is_symlink() for p in paths)
assert not any(p.startswith(x+'/') for p in paths for x in ['scripts','tools','config','catalog','requirements','tests'])
patterns={'model_api_key':rb'\bsk-[A-Za-z0-9_-]{20,}','github_token':rb'\bgh[pousr]_[A-Za-z0-9]{20,}','private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','aws_access_key':rb'\bAKIA[A-Z0-9]{16}\b'}
findings=[]
for path in paths:
 assert not path.endswith(('.lock','.tmp','.pyc')) and '__pycache__' not in Path(path).parts,path
 raw=(R/path).read_bytes()
 for label,pattern in patterns.items():
  if re.search(pattern,raw):findings.append({'path':path,'pattern':label})
assert not findings,findings
(O/'archive-paths.json').write_text(json.dumps(paths,ensure_ascii=False,indent=2)+'\n')
(O/'archive-credential-scan.json').write_text(json.dumps({'status':'NO_MATCHING_CREDENTIAL_MATERIAL','file_count':len(paths),'patterns':list(patterns),'findings':findings,'scope':'Explicit archive paths only; pattern scan is not a universal guarantee'},indent=2)+'\n')
for name in ['archive-paths.json','archive-credential-scan.json']:shutil.copyfile(O/name,D/name);paths.append(str((D/name).relative_to(R)))
# Explicit path batches; force only to include approved immutable package files hidden by legacy ignore patterns.
for i in range(0,len(paths),80):subprocess.run(['git','add','-f','--',*paths[i:i+80]],cwd=R,check=True)
staged=git('diff','--cached','--name-only').splitlines();assert set(staged)<=set(paths)
assert not git('diff','--cached','--name-only','--','scripts','tools','config','catalog','requirements','tests')
(O/'staged-paths.json').write_text(json.dumps(staged,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'EXPLICIT_PRODUCTION_ARCHIVE_STAGED','staged_files':len(staged),'package_files':len([p for p in package.rglob('*') if p.is_file()]),'production_source_changed':False}))

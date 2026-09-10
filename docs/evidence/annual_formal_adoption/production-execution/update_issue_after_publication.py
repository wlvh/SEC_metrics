"""Update the existing execution list after the actual archive and cold read."""
import json,subprocess,re
from pathlib import Path
O=Path(__file__).resolve().parent;R=Path('/Users/lyuhongwang/Developer/SEC_metrics')
def read(p):return json.loads(p.read_text())
post=read(O/'post-archive-read.json');assert post['status']=='PASSED_SAME_PLAN_AND_ACTUAL_PUBLICATION_AFTER_ARCHIVE'
M=read(O/'merge-and-main-sync.json')['merge_commit'];C=read(O/'archive-commit-and-push.json')['archive_commit'];H=post['head'];actual=read(O/'production-verification.json')['active'];approval=read(O/'approvals.json');closures=read(O/'old-pr-closures.json')
live=read(O/'issue28-before.json');current=json.loads(subprocess.check_output(['gh','issue','view','28','--json','body,url,updatedAt'],cwd=R,text=True))
assert current['body']==live['body'],'Issue body changed concurrently; preserve and inspect before editing'
s=current['body'];old=s
url=f'https://github.com/wlvh/SEC_metrics/blob/{C}/docs/evidence/annual_formal_adoption/production-execution'
lines=s.splitlines();idx=next(i for i,x in enumerate(lines) if x.startswith('**更新：'))
lines[idx]=f'**更新：2026-09-10。#31/#33 已关闭且未合并、分支与历史保留；#34 保持 open/Draft；PR40 已用 merge commit `{M}` 合并。固定 Marriott FY2025 候选已正式采纳并发布，归档提交 `{C}` 已推送；原目录 main 与 origin/main 一致且干净。当前正式版本为下列年度采纳包，前驱 R3 保留。**'
s='\n'.join(lines)+'\n'
line=next(x for x in s.splitlines() if x.startswith('- 正式 active 仍为 R3：'))
s=s.replace(line,f'- 正式 active 为 `{actual["publication_id"]}`；manifest文件SHA `{actual["bundle_manifest_sha256"]}`；previous 精确为原R3 `{actual["previous_publication_id"]}`，R3自身仍保留原R2前驱。当前仍 **24指标/240个vNext坐标、327公开行**，最终39指标/390坐标责任不变。')
s=s.replace('### 已发生的真实调用，分阶段记账',f'- [PR40](https://github.com/wlvh/SEC_metrics/pull/40) 已合并并完成同年度来源/执行版本的首次候选特定正式采纳；M=`{M}`，发布归档C=`{C}`。[正式执行证据]({url}/README.md)。这不是新财年发现或剩余指标迁移。\n\n### 已发生的真实调用，分阶段记账',1)
s=s.replace('| PR39 条件收口 + PR40 正式采纳接线工作包新增 | 0 / 0 / 0 | 必要 GitHub 读取及提交实际发生；新生产规则/权限未生效 |','| PR39 条件收口 + PR40 正式采纳接线工作包新增 | 0 / 0 / 0 | 历史开发工作包；当时未激活生产权限 |\n| 2026-09-10 正式采纳、发布及main归档 | 0 / 0 / 0 | 本次新明确委托，真实GitHub批准/合并/发布完成；不挪用旧调用名额 |')
s=s.replace('PR34 保持 Draft、未合并。',f'PR31与PR33已关闭、未合并，分支和transition/执行历史保留（[31收口]({closures["31"]["comment_url"]})、[33收口]({closures["33"]["comment_url"]})）。本次核对纠正PR33正文的历史“未执行”快照：同一计划后续已批准并执行，该轮2/2/0，JPM当时通过、Citi失败；不追认内容正确性，也不重复累加已有调用。PR34 保持 Draft、未合并。',1)
a=s.index('这是项目任务队列，不是运行许可。');z=s.index('\n\n| 工作项',a)
s=s[:a]+f'这是项目任务队列，不是运行许可。先前A/B开发工作包已交付；用户2026-09-10另行明确委托本次真实批准、PR40 merge、main发布及归档。现已完成固定候选的正式采纳；业务调用0/0/0，必要GitHub操作实际发生。当前停点是本轮交付，未授权下一阶段正常新输入实验或剩余指标开发。'+s[z:]
line=next(x for x in s.splitlines() if x.startswith('| [PR40 候选特定正式采纳接线]'))
s=s.replace(line,f'| [PR40 候选特定正式采纳接线](https://github.com/wlvh/SEC_metrics/pull/40) | 已合并，并完成首次正式采纳/发布 | [正式记录]({url}/README.md)：固定plan/包/批准/权限/切换收据、2+238/327、原文回读及main归档 | 本工作包完成后停止；正常新输入、持续许可/触发及后续迁移待另行推进 |')
s=s.replace('正式采纳与生产发布接线及完整待审批包已经交付；**下一实质关口是集中审核并授权首次正式采纳/发布，不是再次读取同一个 69.3%**。','固定候选的正式采纳与发布已经完成；**下一实质关口是承诺范围内正常新输入、持续运行许可与触发的验证，不是再次读取同一个 69.3%**。')
s=s.replace('PR40 新增 v2 候选特定采纳规则和 `issue_28_v7`/V8，均尚待真实生产批准/激活。已识别政策不等于已批准，更不等于具体发布授权。','PR40 新增 v2 候选特定采纳规则和 `issue_28_v7`/V8，现由2026-09-10真实批准和独立激活收据记录本次生效；冻结文件中的历史待审批字段不改。具体发布另由固定plan、真实publication decision、权限及切换收据绑定，不能由政策文件自行授予。')
s=s.replace('最终合并为第2节 main。','历史合并为 `1e97cd08ad26edc1e7a720550811240af1889cb3`。')
a=s.index('**当前工作包：**')
s=s[:a]+f'''**当前工作包：已完成正式发布及main归档。** PR40 merge M=`{M}`，第二父为获审交付`36a91de058ac2fe6aee660a090f2b14d8527deb7`；归档C=`{C}`，最终同步head=`{H}`。PR40分支仍停在获审head，没有追加发布提交。#31/#33 closed/unmerged，#34 open/Draft/unmerged，原分支/stash/worktree均保留。

[正式执行材料]({url}/README.md)绑定固定plan `sha256:6b6c9d2a552fe39392ecf1c72afb0b9b6fe36a61b1a1fd406106b115cc7f0339`、目标`{actual['publication_id']}`及manifest文件SHA`{actual['bundle_manifest_sha256']}`。新包907文件原字节部署，active已切换，previous为原R3；新进程PublicationView回读327行、两项原始来源，2项采纳/238项继承及B03未误选、全部14副本、无pending intent和历史保护通过。归档后对同一既有plan及实际读取入口再作只读核验通过，没有生成新plan。

真实批准为 [Requirement transition]({approval['requirement_transition']['html_url']})、[publication decision]({approval['publication_decision']['html_url']})；[独立公开委托说明]({approval['delegation_notice']['html_url']})明确由Codex按用户2026-09-10对话委托经wlvh账户代发，不表示用户亲自输入，也不是一次新人工代码审查。规则与包内历史PENDING字段未改，生产生效由独立真实收据证明。

完整字段差异已保存：矩阵只有B10 filed_date从2026-02-10变为空，B01保留日期；B10原来已空的字段不重标为新变化。证据表还包含已审来源路径及B01原始来源hash/引用/解析版本更新，数值未变。没有手工补日期或修改固定包。

本轮发布前采证工具失败及首次deploy的OS路径匹配拒绝均保留。首次deploy停在permission写入前，R3不变、无publish预留；隔离验证等价白名单修正后，同一plan/批准部署成功，唯一一次publish完成。未主动生产回退/restore或故障注入。前一开发工作包短暂误写审计兼容副本并恢复的事件也保留，不改写历史。

新增业务调用0/0/0；PR38历史累计仍2/2/0。实际产物和执行证据已在main归档并正常推送，原目录main与origin/main为0/0且完整porcelain为空。Issue28保持开放，三个终点、第5节原则及R4/WB-7/R5/R6/Rf责任继续保留。本次只证明同年度来源与执行版本的首次候选特定正式采纳；本轮停止，不自动开展下一业务阶段。
'''
for a,z in [('## 1.','## 2.'),('## 5.','## 6.')]:assert s[s.index(a):s.index(z)]==old[old.index(a):old.index(z)],a
path=O/'issue28-after-publication.md';assert not path.exists();path.write_text(s)
subprocess.run(['gh','issue','edit','28','--body-file',str(path)],cwd=R,check=True)
verified=json.loads(subprocess.check_output(['gh','issue','view','28','--json','body,url,updatedAt,state'],cwd=R,text=True));assert verified['body'].rstrip()==s.rstrip() and verified['state']=='OPEN'
(O/'issue28-after-publication.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'issue':verified['url'],'status':'UPDATED_IN_PLACE_OPEN','archive_commit':C,'final_head':H}))

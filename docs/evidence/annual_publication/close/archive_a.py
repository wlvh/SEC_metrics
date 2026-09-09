"""Append evidence only after all A run checks and independent review pass."""
from pathlib import Path
import json,hashlib,shutil
BASE=Path(__file__).resolve().parent
REPO=Path('/Users/lyuhongwang/Developer/SEC_metrics')
def read(name):return json.loads((BASE/name).read_text())
binding=read('run-binding.json');review=read('independent-review-a.json')
assert binding['status']=='VERIFIED_CODE_EXECUTION_PACKAGE_BINDING'
assert review['conclusion']=='NO_BLOCKING_FINDINGS'
destination=REPO/'docs/evidence/annual_publication/close'
destination.mkdir(exist_ok=False)
files=['run_a.py','bind_a.py','archive_a.py','post_merge_read.py','zip-verification.json',
    'protection-before.json','executed-commands.json','prepare.json','prepare.log','prepare-execution.json',
    'validate-switch-read.log','validate-switch-read-execution.json','switch-read.json',
    'integration.log','integration-execution.json','integration-checks.json','run-binding.json',
    'ci-implementation.json','ci-implementation.log','independent-review-a.json',
    'fast-implementation.log','python39-boundaries.log','alignment.log']
for name in files:shutil.copyfile(BASE/name,destination/name)
shutil.copytree(BASE/'harness-attempt-1',destination/'harness-attempt-1')
head=binding['code']['head'];package=binding['package']
text=f'''# PR39 最终实现补验

A 实施提交 `{head}` 在原交付提交之后只将 `tests.vnext.test_annual_publication`
接入 fast 白名单。GitHub 原日志证明该模块实际运行4项测试并通过；CI使用PR合并测试
提交，本地首次 prepare 与正向演练使用上面的干净实施提交。具体身份见 run-binding.json。

新根首次 prepare 实际进入来源批准核对、原生图重放、扫描、投影和完整封包，状态
PREPARED_ISOLATED_COMPLETE_PUBLICATION，不是缓存复用。完整验证、switch和
PublicationView矩阵/证据/两项原文读取成功。随后原有两项正向集成测试均通过，
零SKIP：软失败、指针前后中断、受限隔离恢复、回退/恢复、冷读与重复prepare/publish。

- 完整包：`{package['publication_id']}`
- 完整包目录：`{package['directory']}`
- manifest文件字节SHA-256：`{package['manifest_file']['sha256']}`
- 采纳对象内容ID：`{package['adoption_receipt_object_id']}`；它不是收据文件的字节SHA。
- 240坐标=2采纳+238继承，327公开行；B03完整保留但未选中。

run-binding.json由bind_a.py从实际Git对象、执行记录、完整日志、原候选、包内context/
meta/adoption、CI原日志交叉验证。追加本目录仅归档证据；实施到交付的diff另行核对，
不要求日志包含自身未来commit。

独立增量复核来源及亲自执行/材料读取/历史承接分界见independent-review-a.json。
原8项重绑反例沿用父交付记录：本次未修改对应validator或反例，只改变fast选择清单。
这不是再次全仓审核，也不是新增正式发布权限。

外部采证工具首次因gh的text=True字符串未编码就计算hash而失败，原记录及新根保留
在harness-attempt-1；未生成包，未改仓库实现。修正采证工具后在另一全新根成功。
两次必要GitHub评论读取照实记账；故障/冷读完全禁网。业务provider/paid/SEC=0/0/0，
PR38历史累计仍2/2/0。实际R3、原候选、原运行历史、stash和历史worktree未改变。

A仅在最终交付CI、独立复核及全部硬条件满足后允许merge commit。合并后还需
post_merge_read.py只读核验实际R3、原v1包和本轮包。正式采纳/生产权限属于后续B，
本次隔离成功不表示实际R3更新或未来材料泛化完成。
'''
(destination/'README.md').write_text(text)
manifest={str(p.relative_to(destination)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}
    for p in sorted(destination.rglob('*')) if p.is_file()}
(destination/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'path':str(destination),'files':len(manifest)}))

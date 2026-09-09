"""Render actual inert plan identities; only future approval URLs remain unknown."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parent;WORK=BASE/'attempt-02'
plan=json.loads((WORK/'pending-production-plan.json').read_text());binding=plan['binding'];code=plan['code']
output=BASE/'production-execution'
common=f"--plan '{WORK/'pending-production-plan.json'}' --activation-url \"$ANNUAL_ACTIVATION_COMMENT_URL\""
release=common+' --owner-url "$ANNUAL_PUBLICATION_COMMENT_URL"'
text=f'''# 待批准执行计划

计划对象ID：`{plan['plan_id']}`。本文件解释机器计划，不自行授予任何权限。
计划生成于 `{plan['planned_at_utc']}`，对应PR #{plan['pull_number']}。

| 对象 | 实际身份 |
|---|---|
| 政策 | `{binding['policy_id']}` / `{binding['policy_hash']}` |
| Requirement | `{binding['requirement_id']}` / `{binding['requirement_closure_hash']}` |
| 受审head | `{code['exact_head']}` |
| 实现身份 | `{code['implementation_tree']}` |
| 测试身份 | `{code['test_tree']}` |
| 完整包 | `{binding['publication_id']}` |
| manifest文件SHA-256 | `{binding['manifest_sha256']}` |
| 来源快照对象ID | `{binding['source_snapshot_id']}` |
| 原候选文件集合对象ID | `{binding['candidate_file_set_id']}` |
| 原执行 | `{binding['original_execution_id']}` |
| 两项结果集合对象ID | `{binding['selected_results_id']}` |
| 前驱 | `{plan['predecessor']['publication_id']}` |
| 前驱manifest文件SHA-256 | `{plan['predecessor']['manifest_sha256']}` |
| 实际发布根 | `{plan['target_root']}` |

完整包位置：`{plan['bundle_directory']}`。原B01/B10 Run ID、完整前驱指针与全部规则
hash均在机器计划中。两项采纳与238项继承合计240坐标/327公开行，B03不选中。
对象内容ID与文件字节SHA的计算对象不同，不能互换。

## 当前停点

PR40为Draft待集中审核，未自动合并。新Requirement与采纳规则未正式激活，实际
生产grant未签发，实际R3未切换。此计划为首次同年度来源/执行版本的候选特定采纳，
不授予Reader普遍资格，不授权模型/SEC调用，也不是39指标迁移验收。

## 审核批准后按正常入口执行

先审核`approval-templates.json`的两份正文：Requirement transition与独立publication
decision。实际Owner将其作为本PR的真实未编辑评论发布后，才有对应URL。此处唯一
未发生的信息是这两个批准来源及其GitHub时间；没有预填批准ID或签名。

合并必须保持计划指定的PR/受审祖先关系及实施与tests内容；使用merge commit。
合并并安全同步main后，入口核对该PR的真实merge SHA、第二父head及代码内容。
源码/政策/测试改变、目标根、前驱或包身份变化都会拒绝，不能偷偷换计划基线。

以下为已填路径的步骤模板，**本轮未执行生产动作**：

```bash
# 这两个值由上述尚未发生的真实批准提供；不是模型密钥。
export ANNUAL_ACTIVATION_COMMENT_URL='<真实Requirement批准评论URL>'
export ANNUAL_PUBLICATION_COMMENT_URL='<真实publication批准评论URL>'

python3 tools/vnext_annual_publication.py activate {common} --output-json '{output/'activation.json'}'
python3 tools/vnext_annual_publication.py release {release} --operation deploy --output-json '{output/'deploy.json'}'
python3 tools/vnext_annual_publication.py release {release} --operation publish --output-json '{output/'publish.json'}'
python3 tools/vnext_annual_publication.py read --publication-root '{plan['target_root']}' --output-json '{output/'read-after-publish.json'}'
```

每一步重新核对适用规则、真实批准及当前状态。部署只持久化inactive完整包；只有
publish提交单一指针。统一读取返回完整矩阵、证据及两项原始来源，不能仅检查显示数值。
已有完全相同的包部署可验证后复用；操作输出文件不得覆盖原记录。

## 失败与有限恢复

计划范围固定为publish/rollback/restore各一次，recover只属于同一已预留操作。
不存在自动模型/SEC重试，也不会用原PR38剩余名额。

```bash
python3 tools/vnext_annual_publication.py release {release} --operation recover --output-json '{output/'recover.json'}'
python3 tools/vnext_annual_publication.py release {release} --operation rollback --output-json '{output/'rollback.json'}'
python3 tools/vnext_annual_publication.py release {release} --operation restore --output-json '{output/'restore.json'}'
```

有pending intent时先按同一plan/action/permission绑定恢复：指针前中断撤销到旧版，
指针后中断完成已提交新版。没有pending intent且同笔native收据已完成，只确认完成。
预留后尚无intent、或软失败已补偿，则保留旧完整版，本次预留消费；NO_PENDING和
ALREADY_RESERVED都不等于发布成功。若以后决定再试，需要新的实际计划及Owner批准，
不需要再开发发布功能。任何CAS前驱变化、来源/包损坏或权限不符都停止相应写入。

本轮开发中曾发生一次语义扫描默认输出误写兼容副本，已精确恢复并归档；这不是
实际发布。后续准备和演练使用OS级保护，最终审核须同时查看该事件与恢复证据。
'''
(WORK/'PENDING_EXECUTION_PLAN.md').write_text(text)
print(WORK/'PENDING_EXECUTION_PLAN.md')

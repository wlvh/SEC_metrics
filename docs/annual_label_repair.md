# PR38 普通 B10 标签表示修复

本补充修复由同一任务中的owner明确委托，仍保持PR38 Draft、正式R3不变。
原1/1/0失败按原身份保留；新增最多2/2/0、整个相关过程最多3/3/0。第二次仅在
第一次修复验证暴露新问题、完成实际代码修正及新离线回归和独立复核后可用。
修复后的首次真实验证已经成功，新候选 B01 为261.86亿美元、B10为69.3%；
同输入重入新增0调用，累计2/2/0，第二次修复名额未使用。PR38仍为Draft、不自动
合并。[完整交付与边界](evidence/annual_runtime/repair/README.md)集中列明实际证据。

## 确定性规则与取舍

`table_grid._semantic_text` 原有实现只做HTML实体解码、空白折叠和首尾空白处理。
它不删除脚注数字、替换业务词或改变大小写。模型字符串必须精确等于同一已经
定位的单元格 `raw_text` 或 `text`；不对模型输出执行全局strip或模糊匹配。
后续范围判定继续使用程序从来源读回的 `raw_text`。caption仍只允许raw字段。
原失败响应本身不修改，新规则可接收其显示文本；旧RAW规则仍拒绝该响应。

独立调查同时发现继承的范围归属缺口：同表其他组的Worldwide标签，或地区数值
配Worldwide标签，原Checker都可能接受。修复增加有界的行、分组与列验证：

- geography标签与数值必须属于同一个原始行；不能借其他行相同标签。
- population/operating_scope必须来自标签列上最近的、仅一个非空原格的分组标题行。
- 数值列只接受明确的角色/年份两级表头，额外覆盖该列的年份、指标或不支持的表头
  均拒绝；单位还需在数值原格或
  紧邻原格可见，不能借另一指标或变化率列。
- 未知范围或未解决冲突不进入自动成功；不符合此行/组/列表布局的材料明确拒绝。

这些校验不选择替代答案，也没有公司、年度、数值或表格坐标补丁。它们收紧已有
事实标准。更复杂的表头、caption型范围或跨行层级并未由本补充实现证明支持，
不能把这次受限布局成功扩大成任意年度布局的泛化证明。

## 版本和执行连接

新 `issue_28_v6` / V7 engine只增加普通候选修复政策，继承的v1–v5 snapshots和
V1–V6 engines原字节保留。`annual_evidence`从Run绑定的Requirement选择比较与
归属规则；controller acceptance、workflow生成及run_store独立重验使用同一入口。
R4原授权不参与，旧普通候选仍按raw-only解释，不追认原失败Run。

`annual_runtime`继续使用同一个原生B01/B10执行器。第二次资格先校验本轮第一次stage、真实owner正文、plan、两个永久名额和原生
invocation/receipt/marker的完整关联，并重新读取第一次owner评论；不能借旧失败或
篡改一份自报的旧代码字段冒充新修复。阶段许可新增修复回归ID、
独立复核、明确根因及精确input/request绑定。新
[预算委托](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5595412960)
只固定唯一预算目录和上限，本身不允许开socket。每次受审阶段仍由既有Issue
owner评论核对。固定目录中的两个永久ordinal名额与原1次失败合计；换stage、
目录、输入或head不能恢复名额。UNKNOWN及计数不一致不允许第二次请求。

```bash
python3 tools/check_annual_label_repair.py --output <new-external-regression.json>
python3 tools/vnext_annual_runtime.py initialize --data-root <new-external-data> --output-json <new-seed.json>
python3 tools/vnext_annual_runtime.py stage-proposal \
  --stage-root <delegated-budget-root>/stages/1 --data-root <new-external-data> \
  --baseline-run <unchanged-FY2024-successful-run> --review-file <independent-review.json> \
  --repair-evidence <new-external-regression.json> --repair-ordinal 1 \
  --output-json <new-stage-proposal.json>
```

proposal先重建回归并核对review，再形成明确请求；不能用自报字典代替通过的回归。
真实run仍用 `--approval-url <owner-stage-comment>` 和新输出文件。
历史数据/规则副本仍按字节验证，Python始终从原checkout执行。

## 回归与当前证据

`check_annual_label_repair.py`使用未经修改的原失败响应，覆盖旧规则拒绝、新规则
接受、原正确标签不回归，以及数字、单位、期间、表/原格、脚注、未知别名、
跨行相同标签、错误地区数值、相同数值错误分组和冲突等反例。没有模型请求。
`tests/vnext/test_annual_repair.py`还仅在GitHub/provider外部边界注入测试响应，
验证同一完整原生运行、重复输入零新增、失败保留及第二名额不能原样重抽。
测试批准和LIVE形状计数均明确是模拟记录，不能被真实额度或资格引用。

最终受审和执行代码同为 `bb7e3f35198c662b9f36dbd433e6fd7b30284526`，独立代码
复核和独立原文核对均通过。23项正反回归、两项原生运行回归、26项标签及输入/
检测测试、Python3.9标签四项、本地33项fast及该head CI通过；细项与重叠范围见
[测试记录](evidence/annual_runtime/repair/test-verification.json)。

本次[具体阶段记录](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5596431062)
由Codex依用户委托在复核及测试通过后登记。新请求HTTP200，实际输入161707、
输出580；assistant正文与原失败完全相同，仍未带前导换行，但原生新Evidence、
SYSTEM Review与Result成功。新request ID、原始响应envelope及execution分别保存，
原失败未追认成功。再入返回NO_NEW_ANNUAL_FILING/NOT_EXECUTED，新增0/0/0。
新旧普通候选的OPEN状态、R3的独立正式状态和来源字节区别均如实列入对照；
这不是未见材料泛化、长期运行许可或正式发布证明。

<!-- capability-anchor: CAPABILITY.annual_b10_label_repair -->

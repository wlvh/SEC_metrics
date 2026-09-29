# 精确差异独立审阅：2cffa8e99a724e1f4015c6c0c17b1d7e24846aa2

**结论：CHANGES_REQUIRED。** 相对父提交 `3fa513864d9f50ea5aef8e33f41ffdb4b0831b4d`，Ford FY2025 原件的金额拆分和当前私有 B03 计算有直接依据；但新增通用来源关系规则会接受明确否定“包含”的现金流表标签。这是可复现的误接受，修复前不能认可这条新路线的完整语义护栏。当前真实 Ford 原件没有该否定句，因此本发现不推翻该原件中的 `15,974 = 7,834 + 8,140`，也不把私有候选升级为正式结果。

## 需修复的发现

**[P2] 现金流表的否定包含关系仍获来源证明。** `scripts/vnext/b03_exact_impairment_relation.py:20-22` 的 `_IMPAIRMENT_COMPONENT` 在 `asset impairment` 与 `including depreciation of` 之间允许任意 160 字符；`not including depreciation of $8,140` 因此仍命中。`prove_exact_impairment_relation` 在第 115–121 行只检查正则命中、文本金额与原生事实金额一致，没有拒绝同一子句中的否定。以 Ford 已保存原件为底，仅把唯一一处现金流表标签的 `including depreciation of $<ix:nonFraction` 改为 `not including depreciation of $<ix:nonFraction`，更新临时副本的来源 SHA，其他事实、数值、context、分部附注均未改变；函数仍返回 `exact_impairment_depreciation_usd=8140000000` 和 proof ID `sha256:a7ed745b889dba4ed2c4107e9512a9f7ed9d1d1070b62782175b00806d44720c`。这份修改后的原文在现金流表中明确否定包含关系，和分部附注直接矛盾，应拒绝作为精确扣除的证据。第 34 行的后继 `prepare_case` 直接消费该证明，故错误可进入新 B03 候选。请将正向关系绑定到未被否定的同一标签子句，并加入此负例；现有 `excluding depreciation` 负例没有覆盖 `not including`。

## 已核对且未发现阻断的部分

- 在 SHA `3bbda349…` 的原始 Ford 10-K 中，分部表 `table_000148` 的 2025 年无维度 D&A 总额为 15,974 百万美元，标 `(g)` 的 Model e 分部值为 8,235 百万美元；相邻脚注说其中约 8.1 十亿美元为 Model e 减值相关折旧。现金流表 `table_000079` 的同一 `c-1` context 有“Depreciation and tooling amortization” 7,834 百万美元，另一个行标签明确写“including depreciation of $8,140”，其内联原生事实为 8,140 百万美元。精确算术成立；`Other amortization` 行不是本次的无形资产摊销输入。Issue #28 当前正文已记录“不加回减值”的业务决定，本补丁没有仅凭约数推算 8,140。
- 默认 `normal_run_v3.prepare_case` 在 Ford 仍重建旧 Result ID `sha256:1829d73dac66a195a590ab84ea1f1d1800a77fae60d828b6f37d5cbeec2abd30`；显式后继重建新值 `-0.007128858795196163766173431518` 和新 Result ID `sha256:06d93be4d329b7705642879ea50c677250b35c646214070e92f8e009396d9289`。新增路线经原生 Run/重放分支，不是直接改写旧 Result。提交者的私有运行及异进程冷读日志均为成功；本审阅未重跑这些长材料。
- 对父提交与本提交做 AST 对照，`prepare_case`、`_binding`、`install_normal_inputs`、`_install_case_inputs`、`create_normal_run`、`_create_case_run` 函数体相同，仅 `replay_case` 新增显式路线分支。默认绑定的**字段形状**未改；V13 闭包从 `sha256:7ff85129…` 变为 `sha256:eb4ffdd4…`，所以新默认绑定的 `requirement_closure_hash` **值**会改变。不能据此宣称与 #47 旧闭包字节等价；未读写 #47 或 PR52。当前 V13/V14 闭包与 V14 语义及三份接线收据的只读验证通过。
- 两项获准短测分别为 1/1、2/2 通过。提交者的 `fast.log` 记载 142 个本地 selector 通过；`affected.exit=1` 的初次失败与后续单项回修成功都保留。`native-v14` 试验失败，最终路线实际绑定 V13，不能将试验记为成功。完整外部材料长测按其条件跳过。本审阅没有真实 provider、paid 或 SEC 请求，也没有正式采纳或 active 切换。

审阅仅覆盖委托所列差异及证据。修复上述误接受后，需对**新精确补丁**重新做该负例、原 Ford 正例和最终绑定检查；本结论不自动传递给后续 head。

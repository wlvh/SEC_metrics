# 62243bf 限定范围证明增量独审

结论：**CHANGES_REQUIRED；原 P2 的两个已执行包装反例已修，原 P2 尚未完整闭合。** 本轮不覆盖或撤销 `../independent-review/conclusion.md`。其原 Spec/Calculator/default 接口、来源身份、Pfizer FY2023 数值与其他未变结论按原绑定直接继承。本轮仅审 `83eaa4da5d18c7accc0c093b1ef4db5f5158da16` → `62243bfdce042a79508f242df65cc897fcfaf035` 的新 `_statement_scope`、demonstrated-split 调用位置、ordinary current 配置增量及相应 scope 测试。

## 遗留 P2：一行含 native 金额就免检整行，独立说明仍被忽略

定位：`scripts/vnext/selected_revenue_scope_v1.py:73-79`。

新代码把任何含 `contextRef` 原生标记的整行加入 `native_rows`，随后 `continue`，所以该行其余未标记文字也不再进入 `unknown`。原生事实只能赋予对应数值的主体/期间/单位含义，不能证明同一行的说明没有缩小整表范围。这是原 P2“同表直接排除说明不能被 context 盖过”的剩余一条路径，不是要求增加通用自然语言规则。

一个具体的有限输入：保留现有 `originals()` 的标题、收入区段、所有 facts/金额/期间/单位，仅将总额之后的净利润行标签由 `Net income` 改成 `Net income; Total revenues exclude operations of Subsidiary Beta`，并按现有 fixture 方法更新 primary 的 source SHA。净利润的 `ix:nonFraction` 原样保留，XML 数值不变。该说明与新测试 `test_explicit_local_exclusion_is_not_overruled_by_same_context` 的字面排除条件相同，只改变所在 HTML 行。

代码路径可以直接核定：净利润行有 native ordinal，被 78–79 行整行跳过；标题/caption 不变；收入区段、期间、单位、三项 primary/XML 数值和加总不变；171 行 `_statement_scope` 返回空 unresolved annotations，后续仍可形成 `complete_scope_proven=true` 并筛出原产品收入候选。整表 span SHA 会保存这些文字，但保存 SHA 本身不等于已检查范围矛盾。

**此变体是本轮代码追踪的具体反例，未额外执行。** 委托仅允许指定 scope-suite 命令，本轮遵守该限制；不能把它写成已运行反例。新测试目前只覆盖纯文字独立行，未覆盖含数值原生 fact 的行上追加范围说明。旧审阅已运行的两项误接受反例仍按旧证据解释。

推荐限定修复：保留 native 数值单元格和其必要标签的原验证；不要以“一行存在 native 值”为理由豁免该行未归属的解释文字/额外说明单元格。至少对上述同字面限定、不同 HTML 位置的输入准确拒绝，保留已验证 Pfizer23 正向。无需穷举英语、改 Spec/Calculator 或扩大指标口径。

## 已通过及复用的责任

- 指定 suite 的 21 项测试全部通过，0 failure/error/skip，0.189s，见 `directed-tests.log`。原受限 caption 现在抛 `STATEMENT_CAPTION_SCOPE_UNRESOLVED`；独立纯文字排除行抛 `STATEMENT_LOCAL_SCOPE_UNRESOLVED`；合并标题后限定语及无合并标题也被新测试拒绝。这两项原已执行反例的当前包装已修。
- `_statement_scope` 真实位于至少两项收入组成被证明后的分支内。`len(parts)<2` 在范围/单位新增证明前退出，继续 `NO_DEMONSTRATED_SPLIT` 而不授完整范围。单项完整客户合同收入正向测试通过。Salesforce 实际大材料未重跑；本轮仅确认这条分支不会新增全表 title/annotation/unit 证明。README 对 Python3.14 Salesforce 正向的描述是开发保存证据，不冒充本轮独立运行。
- `p2-actual-calculator.json` 的新增 statement_scope 保存原合并标题 `Consolidated Statements of Income`、随后 `Pfizer Inc. and Subsidiary Companies` 的各自原文/span/hash，以及 table_000113 的 span/hash。实际保存的 Product 50,914m + Alliance 7,582m = Total 58,496m，2023-01-01…2023-12-31，XML MATCH，新 Result 128c170a…86da/58,496,000,000 保持。它仍为原件/Calculator 候选证据，非 FY2023 公司入口或正式采纳。本轮复用旧原件核验，未读取 peer/#47 原件树或重解析财报。
- `p2-tested-tree.json` 的三项 program SHA 全部与当前 62243bf 文件相同。p2 actual 保存 uncommitted/base 记录，不改写成 exact-commit 运行；本轮短测试才在已核对的当前 HEAD 上执行。
- `p2-current-company.json` 保存必要配置变更后 first/repeat/reader exit 0、调用 0/0/0、结果 62,579,000,000 与原 536f3b12…ee1bf 身份、NO_DEMONSTRATED_SPLIT/complete_scope_proven=false。只读 SHA 重核本地临时 state 的七份旧结果和新增七份结果，14/14 与记录相同；旧七份在两个记录中一致，重复文件一致记录保留。没有重新执行公司 CLI。
- ordinary_current_update 的 B01/B03 配置确实加入实际调用的 `composite_scope.py`，移除 B01 未消费的 `reported_monetary_literal.py`；政策 rule/presentation paths 不会重新将后者加入。B03 自己的分支继续绑定 reported_monetary_literal。此次只验证所改配置行的真实/无关依赖，不扩为全依赖闭包审计。

## 验证边界与操作

唯一执行的测试命令：

```text
PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-company-c02-venv-20261006/bin/python tests/required_unittests.py tests.vnext.test_selected_revenue_scope_v1
```

未运行公司/完整财报/额外 suite/远端 CI、网络、SEC/provider/paid、生产动作、spawn、commit 或 push。未写产品/tests/旧证据/peer 树/ledger。唯一新增目录文件为本 conclusion、directed-tests.log、evidence-inspection.log。

工具总量按包装与嵌套分别计：9 次 functions.exec + 9 次 exec_command = 18 次（含最终只读状态核验；上限 20）。普通消息 2 条（开工说明与最终报告）。轻量记忆检索无相关命中，未以记忆替代本轮证据。到此停止追加语义反例和旧模块审阅；需解决的是上述单一遗留 P2。

结论保存 UTC：`2026-10-09T21:23:39.109123+00:00`。

# c5a46ff 包含行修复的限定独立审阅

**结论：NEEDS_FIX。原 P2 的数值反例已被修复，但包含行自身的倍率仍未核对，存在一项 P2，不能授予这次修复的无问题独审结论。** 真实 Ford 正例、默认兼容及定向小测成立；未发现完整 B06 数值被错误发布。

## 范围与历史

- patch：`c5a46ff556afacbc29e6fc9cfc8f720e068c2baf`；差异 base：`508c4346d33d11fe218edd449c88d66d92564695`；开工和终检 HEAD 均为 patch，三个审阅文件与该提交逐字节一致。
- 只审 `industrial_lease_relation.py` 的新增包含行金额/列/倍率逻辑、`ordinary_special_debt_scope.py` 的显式 scale 传递及对应小测。必要只读追踪 `_numeric_xbrl_value`、已有原件解析和表格定位；未重审全模块、完整财报、公司 Run 或长链。
- 先读取 `../independent-review/conclusion.md`，继承其未变范围和原 NEEDS_FIX 历史。原 508c434 的结论及日志不改；本次不能将旧失败改记通过。
- 已实时读取 Issue #28 正文（updatedAt 2026-10-07T20:09:47Z）及本工作树 AGENTS。按受信任内部工具规则保留业务核对；本文的反例检验普通来源/程序失误，不建设防执行者作弊机制。

## P2：借用总债务倍率，把包含行已知的金额冲突盖掉

定位：`scripts/vnext/industrial_lease_relation.py:61–70`；相关显式传递 `ordinary_special_debt_scope.py:90–91`。

本次修复从总债务原生事实取 `reported_scale`，先证明总额可见数字按这个倍率等于总额原生数，再用**同一总额倍率**解释包含行的纯文本。包含行本身已有原生事实，但程序不读取它的单位、倍率和值。验证了总额倍率，并不能证明包含行也采用该倍率。

真实原件当前工业列的包含行为 `us-gaap:OtherLoansPayableCurrent`，HTML ordinal 2443、id f-2427、context c-696；可见226，原件自身 scale=6/USD，XML为226000000。原表说明“in millions”，工业当期列 index9/span2。真实来源下它与136000000租赁兼容。

独立有界反例在内存中仅改变这一个包含行事实：HTML保持可见226、USD、主体/期间/维度/列/标签及其他全部事实不变，只将该事实 scale6改为3；XML将对应值226000000改为226000。两份模拟原件分别重算 raw_asset_id，没有写回来源，也没有获取信用。实际原生解析独立确认两份含行金额均为**226000 USD**，当前租赁仍为136000000，总债务仍为5550000000。公开 `inspect_special_scope(..., reported_relations=True)` 仍输出：

```text
两份原生包含行金额 = 226,000 USD
当前租赁 = 136,000,000 USD
当前总债务 = 5,550,000,000 USD
保存的 inclusive_amount = 226,000,000 USD
借用的 reporting_scale = 6
lease_inclusion.status = REPORTED_INCLUDED
additional_debt_amount = 0
```

这是一条已知的可见表说明/包含行原生倍率冲突，以及“包含行 < 租赁 ≤ 总债务”的直接矛盾。程序应保留 UNRESOLVED，不能自行忽略行自身数据而确认包含。它不说明真实 Ford 披露错误，只证明新增检查仍漏掉限定范围内的单位/倍率失误。反例完整输出、上下文和模拟字节摘要见 [independent-carrier-scale-conflict.log](independent-carrier-scale-conflict.log)。本次未实施修复。

建议限定修复：当包含单元格有原生事实时，读取并核对该事实自己的单位、倍率、金额和相应原件值；与表的单位说明或总额倍率发生直接冲突时保留 UNRESOLVED。将上述两份原件一致、包含行自身 scale 变化的反例纳入小测。无需扩建完整 B06，也不能以当前最终仍 WITHHELD 代替部分关系正确性。

## 已确认的行为

1. 指定 unittest **10/10通过，0.001s**。原数值反例（包含行226百万、租赁1000百万、总额5550百万）通过指定重现脚本得到 **UNRESOLVED/null**；见 [unit-tests.log](unit-tests.log)、[carrier-conflict.log](carrier-conflict.log)。原 P2 的这条具体路径已修好。
2. 独立新增 **17项定向检查全部符合预期**：有效0/6倍率正例、等于包含金额边界、非当前包含行不足、正确当期列5/另一列999、缺当前列、span不符、重复origin、非USD总额、总额可见/原生矛盾，以及带单位/货币/百分号、负数、括号负数和空字串。见 [independent-controls.log](independent-controls.log)。这些检查不覆盖上述包含行自身倍率遗漏。
3. 保存原件正例经实际 `prepare_special_debt_case` 重建：工业总债21919000000；当期包含226000000、租赁136000000；非当前包含1210000000、租赁754000000；两段column9/span2，scale6；总租赁890000000，追加0。原件片段证明表单位为百万及包含行自身标注scale6。见 [real-source-and-default.log](real-source-and-default.log)、[carrier-original-fragments.log](carrier-original-fragments.log)。仍保留工业归属权益和债务完整性两项限制，definition_complete=false、ratio=null、B06 WITHHELD/null。
4. 从差异 base 用 `git show`在内存加载旧 scope 实现，对同一保存来源核对**整个默认 case**：base默认 == patch默认 == patch显式False。整个对象JSON摘要 `e7f2b73ec428d34bd2ef57269cab434596939ff8ffb7c5211bc8d5961bc6feb8`。没有发现默认接口退化。本次没有重跑开发者保存/读回脚本；开发保存一致只能作为其原有记录，不能提升为业务完整性。
5. 原件末次摘要仍为 HTML `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`、XML `35cb6e0ef1f84d5790c0fdf38abb363b92b65cd7f14ab8e0342968780e9efcfe`。只复用旧完整阅读范围，未冒称本次重读完整财报。

## 执行与资源

- 首次捕获UTC：`2026-10-07T21:28:24+00:00`；结束UTC：`2026-10-07T21:32:59.261164+00:00`；捕获区间 275.261秒（含本次结论写入，未触及90分钟上限）。
- 工具调用总计 **31**：9次外层 functions.exec、21次嵌套 exec_command、1次 write_stdin；包括最终写结论/日志与HEAD、源码字节、原件核验。80上限未触及。
- 普通消息 **3**：开工、一次进展、最终报告；问题0。未spawn或nested spawn。
- 新增真实 provider/paid/SEC/账户请求均0；GitHub只读 Issue #28一次。没有commit/push、#47操作、tar、真实模型、长测试、完整Run/CSV/生产/active动作。
- 只新增本目录一份 conclusion.md 和七份日志。源码、原件、旧证据不改；终检 tracked diff为空。

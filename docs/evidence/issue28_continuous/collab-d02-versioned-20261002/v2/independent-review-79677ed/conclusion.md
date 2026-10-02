# D02 Item 8 V2 限定独审 — `79677ed2c8519a952698ee2a0b05e24deb91702a`

**结论：NEEDS_FIX（P2，新增显式 V2 路线）。** 审阅范围仅为该提交相对父提交的差异，不改变旧 `de22326d` 的 NEEDS_FIX 或 `0ccf5363` 的 PASS_GATE_ONLY 记录。程序已能把 V2 明确选入普通更新、保存并冷读私有 Run；但 V2 仍可将明说本公司面临诉讼的段落当作无关类别清单删掉，不能把这次限定接线当作 D02 内容正确或当前390信用。

## P2：时间状语加 “our company” 时，真实诉讼被误当作清单

反例：`During 2025, our company faced litigation, regulatory proceedings and fines.` 这句话的主语是本公司，动词 `faced` 明确将诉讼列为本公司面临的事项。以当前 D02 的 `_LEGAL` 关键词调用 V2 `classify()`，得到 `litigation → LIST_MEMBER`、`exposure=[]`、`left_out=True`；经 `ordinary_d02_item8_v2.select()` 后，这个 `ITEM_8` 块被写入 `item_8_category_mentions_left_out`，不再出现在 D02 候选中。只把主语改为 `the Company` 或 `we`，同一结构的 `left_out` 即为 `False`。

根因在词表的 `registrant_subject` 只认 `we` 或 `the Company/firm/...`，未认 `our company`；`first_person_subject` 只认 `we`，当前曝光关系也不识别 `faced`。前置时间状语后的逗号使该词落入非首列表项，`_structure()` 遂按协调清单处理。相关实现为 `catalog/r6/D02_item8_category_28_v2.json` 的主体模式、`scripts/vnext/d02_item8_category_28_v2.py` 的 `_governed_by_the_registrant()` / `_structure()` 与 `classify()`。这是函数及选择器级合成反例；没有证据表明当前 Lumen 私有 Run 实际含此句，也没有对十家公司全部候选做内容验收。修复应让无法证明为纯类别提及的段落留在候选，保留本公司确实卷入事项与普通顾问成本清单的正反例，而非默认放行所有背景。

## 通过且边界清楚的部分

- 旧 V1 规则文件和旧更新包装器在父子提交的 Git blob 完全相同；`d02_category=True` 在新 Run 和更新入口仍于写入前被拒。默认 `False` 的函数签名、原候选行为不变；`ITEM8_V2` 才选新版规则，普通 CLI 指向专用 V2 包装器及 `metrics/D02-item8-v2` 状态根。
- 新规则、选择器、包装器、调用链与 V13/V14 未冻结绑定及三份接线收据相符。本人在本地精确 HEAD 执行 `validate_execution_authority()`（V13/V14）、`validate_semantic_rule_bindings()` 和 `validate_wiring_receipt()`，均通过；闭包分别为 `sha256:f5f6bf76…`、`sha256:9e4e95c0…`。旧已保存包未被本次重签。
- 指定短测 1/1 通过，确认已知两句 V1 误删反例在 V2 中保留、旧 V1 继续停用。本人直接重建并读取 Lumen 原件第1670块：讲的是聘请外部法律顾问就融资、监管、诉讼等事务提供建议及相关费用，V2 将其移出 D02 与这段原文一致；另读取 Pfizer 2175/2240、Paramount 2108/2257 的来源片段，未据此声称全部候选语义验收。
- 提交方的最终树日志记录 Lumen 私有 `CANDIDATE_READY`、独立进程回读与 `NO_SOURCE_CONTENT_CHANGE`，Result ID 未变；这是已读取的执行材料，本次没有重跑完整原生 Run/冷读，也不把日志的 Evidence `PASS` 解释成其余14段都内容正确。新私有结果未进入可信390。

需要补上述反例和一条顾问成本类别清单反例的有限回归，修补后仅复核实际新差异及受影响的保存/回读路径；本结论不要求重跑既有未变的大材料。

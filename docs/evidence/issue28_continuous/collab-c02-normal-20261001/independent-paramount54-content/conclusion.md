# Paramount FY2025 C02：54 条私有摘录内容独立核对

**结论：NEEDS_FIX。** 原件、同主体及年度归集、54 条全文的原始字节定位和 Result 传递均核对成立，但当前摘录集合漏掉了同一份 10-K/A 中明确的董事任职起点及任职资格说明。`PUBLISHED` / `EXACT` 是原生流程状态，不能给这份业务内容完整性信用。本结论只针对代码 `c6eac2918aabf5227c0559b07a43f2bce4e3fb73` 的 Paramount FY2025 C02 私有 Result；不改变其身份或历史记录。

## 来源和复核范围

- 保存的 SEC submissions 清单标识 Paramount Skydance Corporation、CIK `0002041610`。FY2025 原 10-K `0002041610-26-000011` 于 2026-02-25 申报；补充 Part III 的 10-K/A `0001140361-26-016758` 于 2026-04-24 申报，二者 `reportDate` 都是 `2025-12-31`，均在同一 CIK 的保存清单中。10-K/A 封面明说它为原 10-K 补入 Part III Items 10–14；原 10-K 和修订件均说明 2025-08-07 成为 Paramount Global 的 successor issuer。这里核对的是后继登记主体的披露，未把前身董事会或 2025-12-31 当成董事人数的测量时点。
- 10-K/A 保存 HTML 的 SHA-256 为 `10fcfbc33813d251dcaf024cf7ac96adc2a4971d7cc1424eed25affb470ff7d0`。从该原件重建出完整的 1,596 个文本块及相同的 document ID `sha256:4c170c897e0369df164311233783f6aac9d043f5a225781c7879a7ed22f784df`。54 条候选逐一与原件块全文、起止字节、片段 SHA-256、source reference 及 Result 的 54 个同序文本项比较，无机械不一致；固定选择器在该原件上也重现相同 54 个块。逐条哈希与漏选原句见 `source-and-coverage.log`。
- 逐条阅读 54 个全文；在全部 1,596 块中定向找未选的董事人数、独立性、委员会、资格和任职变化表达，结合上下文排除法规标准、委员会职责、薪酬、其他组织的董事会及纯交易内容。这个查找足以指出下面的实质漏选，不主张穷尽所有可能说法。

## 可复现的漏选

修订件的董事介绍不是一般资历背景而已。下列八个未选块同时写明某人 **“has served as a member of our Board since”** 的起始时间，以及发行人 **“We believe [name] is qualified to serve as a member of our Board because”** 的资格理由。Thornton 的两类事实分列在相邻块 166、168：

| 原件块 | 董事 | 任职起点 |
| --- | --- | --- |
| 100 | Andrew Brandon-Gordon | 2025-08 |
| 110 | Barbara M. Byrne | 2025-08 |
| 117 | Andrew Campion | 2026-01 |
| 126 | Gerald Cardinale | 2025-08 |
| 133 | Safra A. Catz | 2025-08 |
| 143 | Justin G. Hamill | 2025-08 |
| 150 | Sherry Lansing | 2025-08 |
| 159 | Paul Marinelli | 2025-08 |
| 168 | John L. Thornton | 资格理由；任职起点在紧邻的块 166（2025-08） |

上表最后一行的两个事实分列在块 166、168；块 168 本身没有起点句。其余八块同时载有两类事实。所需含义来自本方 `catalog/r6/C02_board_disclosures_v2.md` 的“董事会成员变动”和“董事资格认定”。例如块 117 明确区分 Campion 于 **2026-01** 加入，不能靠块 84 的现任十人名单推成他在 2025 年末已经任职。块 110 明确写 Byrne 曾任前身 Paramount Global 董事，但句首另写她自 2025-08 起任**本登记主体**董事，不能因前身经历而整体排掉。Ellison 的同类介绍块 92 因同时写董事长身份被选中；其余这些任职及资格事实没有等价的所选原句。单独的 `Director since: 2025/2026` 卡片字段未作为本结论的独立漏选依据。

本方选择器的 `statement_labels()` 只覆盖特定资格措辞，并未为这些 `We believe … qualified to serve` / `has served as a member of our Board since` 句式建立完整接受路径。#47 固定 `60aa9f7b…` 的判读和裁决只用于定位可能位置；本结论来自本方保存 HTML、相同源记录和逐句判断，不继承 #47 的验收信用。

修复应在共同选择器范围内使上述实际的本公司董事任职与资格句能进入候选，同时保留对其他组织经历、抽象政策及纯任职年限的排除；之后由 #28 对这个 FY2025 私有来源重新独立核对完整性和 64 条上限。当前 54 条不能登记为 C02 构成事实业务通过，也不能由本结论推及正常生产采纳。未执行真实 SEC/provider 请求、commit、push、生产入口或结果身份变更。

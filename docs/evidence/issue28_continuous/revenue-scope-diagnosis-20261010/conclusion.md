# 指定 Pfizer FY2023 B01 小计误接受的离线诊断

诊断基线：`f6ef7886d6630f7675c25cd42e306c373ab05769`。指定错误 Result：`sha256:a6e31052ee3e389e46442777fa69c0d06c6ec43e847dd65c412c0e05509aa8f7`。证据版本：`0dc5de75:docs/evidence/issue47_growth_reference_20261010/` 中明确指定的 README、pfizer-native-revenue.json、pfizer2023-revenue-tables.json。代码通过 git 对象读取，没有切换/修改 branch。

结论：50,914m 是已报告且金额正确的 Product revenues，58,496m 才是该申报的 Total revenues。错误不是数值解析、币种、年度或公司身份错，而是把“同概念的原件金额相同”当成“已涵盖 B01 要求的收入总范围”。两个原件都准确保存同一个分量，所以 primary/XML amount-match 完全可以通过。修复必须在原来源读口证明收入量的范围，并在现有 Calculator 选择前排除已证明属于分量的候选；本原件已有合法总收入，不能止于扣留小计。

## 原件核对

只读指定 source-inputs 的保存请求日志定位两个确切文件，再重算原件 SHA。必要日志见 `raw-check.json`，它是标准库只读原件检查，不是运行公共解析器、指标或公司 pipeline 的证明。

- primary：`evidence/request_attempts/e8/e8439987e90aeb5170db8daf9cddf9c2c9e2a4567c87ef8e4bc6722a83c905c0/pfe-20231231.htm`；实际 SHA 为 `e8439987e90aeb5170db8daf9cddf9c2c9e2a4567c87ef8e4bc6722a83c905c0`，5,349,302 bytes。
- XML：`evidence/request_attempts/6d/6df3a97b0eb241874df90b56e526de28b36234349c6c4cc2e47e1fca5eee4291/pfe-20231231_htm.xml`；实际 SHA 为 `6df3a97b0eb241874df90b56e526de28b36234349c6c4cc2e47e1fca5eee4291`，6,740,193 bytes。
- primary 的 table_000113 明列 `Year Ended December 31,`、`(MILLIONS, EXCEPT PER SHARE DATA)`、2023/2022/2021。

| 原表行 | FY2023（USD million） | primary ordinal / concept | 原生范围 |
|---|---:|---|---|
| Product revenues (a) | 50,914 | 97 / RevenueFromContractWithCustomerExcludingAssessedTax | 收入分量 |
| Alliance revenues (a) | 7,582 | 100 / RevenueFromCollaborativeArrangementExcludingRevenueFromContractWithCustomer | 另一分量 |
| Total revenues | 58,496 | 103 / Revenues | 同一收入区段的总额 |

三个事实都是 c-1：CIK 0000078003，2023-01-01 至 2023-12-31，无维度；inline unitRef=usd、scale=6、decimals=-6。50,914 + 7,582 = 58,496。XML 的同 context 分别保存 50,914,000,000 和 58,496,000,000，并有总额重复披露。指定表证据另保 table_000273/000276/000280 的总额 58,496m，ordinal 2997/3038/3071。这些重复支持一致性；不能把它们当相互独立的会计范围证明。

原件中 Total revenues 的存在、同表收入分量的包含关系、同一年度/主体/单位和原生金额共同支持本结论。没有用“哪个数最大”、concept 名称或一个关键词单独推定全收入。

## 实际代码链与缺口

1. `catalog/metrics/B01_revenue.md:18-25` 把客户合同税外收入排在 Revenues 前。该 Spec 文本说复用 Company Facts 选择语义，没有显式机器字段证明 total scope。
2. `calculator.py:_select_structured_fact`（216-307）按 approved_concepts 顺序选择；首先存在的匹配年度/主体/FY/10-K 候选即返回（251、260-265、303），不会因为后面有更完整的 Revenues 自动改选。目标 accession 有候选时优先该申报；这并不能辨别同一申报内的分量。
3. `selected_income_source_v1.py:native_income_reports`（60-100）核对原件 hash、accession、公司、DEI 年度、官方 namespace、USD、原生 context/无维度和金额。它返回全部已批准 concept 的原生事实，但没有取原表行及收入区段包含关系。`check_visible_short_period` 只给起始日不同的短期间做可见列检查；本全年 c-1 不触发，且即使触发也只证明期间。
4. `ordinary_income_input.py:verify_income_observations`（180-196）按照已选 observation 的同 concept、同期间找 primary/XML，执行 precision_choice 后比金额（188-194）。对 50,914m：原件中确实有同 concept、同金额，所以接受。它不比较 observation 与原表 total，也不检查另一个批准 concept 的涵盖范围。无维度 context 只证明没有 XBRL 分段维度，不能证明该 concept 表示收入总额。
5. `historical_statement_cases.py` B01（259-293）先用 Company Facts 执行 calculate_metric，成功后才读取两类原件并调用上述同概念验证。这个次序只能确认先前选择的金额，不能在选择前使合法总收入候选胜出。
6. `normal_zero_ai_results.py` B01（259-265、276-294、330-331）还存在接入差异：prepare_current_income_input/verify_income_observations 只在 SUCCESSOR_REGISTRANT_ONLY 的 income_input 非空时执行；CONTINUOUS_PRIMARY 的普通 B01 不统一走此核对。不能只修历史消费者而称当期 B01 已覆盖。
7. `ordinary_income_input.py:prepare_current_income_input`（145-164）自身也按同样 concept 顺序挑首个收入金额；因此把它原样扩接到普通 B01 仍会保留本缺陷。

代码阅读支持这条因果链。没有读取指定 Result 的完整记录/Trace，也没有重跑失败 Result；Result 身份与既有显示错误来自委托及固定证据，因此不声称动态复现了该 Result 的执行。

## 最小修复位置与正向接入

建议把源范围证明放进现有 selected_income_source_v1 / ordinary_income_input 接口，保留原生事实解析器及 Calculator 的单一责任。源码本轮没有修改，下面是实现建议。

- 在 selected_income_source_v1 的原生收入事实读口，针对 B01 收入候选追加绑定原件的量范围证据：用 `_InlineTableIndex` 和 `_fact_cells` 把每个事实 ordinal 精确连回原表单元格；保存 `_cell_proof` 的行、列、table_id、grid_sha256、原始标签及来源引用。证明目标年度收入区段的总额/分量关系，保留表头、必要同区段行及关联脚注。检查范围限定于 B01 必需的完整收入区段，不建立财报通用语言解释平台。
- 原生官方 concept、USD/context/主体/期间、`_source_value` 以及 `precision_choice` 保持复用。表结构和数值相加只是支持证据；必须是同范围、同期间、原件明确报告的收入总额，不能把任意可相加行或最大值当 total。对本例使用原生 `Revenues` 的报告总额；无需为 Alliance 引入新的 B01 approved concept 或人工加总指标。
- ordinary_income_input 在现有准备/验证接口中返回并要求这份收入范围证据。过滤的是已证明不满足 B01 收入范围的候选事实，不修改其数值、concept、fact_id 或历史记录。非收入 observation（例如 B03 其他组成）不套用收入 total 规则。
- 两个消费者在 calculate_metric 前接入同一份来源范围准入：历史入口把 287-292 的原件收入检查移到选值之前，并用其结果筛选已有 `facts`；普通入口对 B01 的 CONTINUOUS_PRIMARY 和 SUCCESSOR_REGISTRANT_ONLY 一致接入。之后仍由已有 calculate_metric 在合法事实中按原 Spec 顺序选择。B03 的 B01 依赖须消费相同准入结果，避免依赖与单独 B01 选择不同口径。
- 本例筛去客户收入 50,914m 后，已有 approved `us-gaap:Revenues` 在两原件内提供 58,496m；它进入原 Calculator，产生新的 B01 observation/trace/result，值为 58,496,000,000 USD。这是正向完成路径，不是给旧 Result 换值。若 Company Facts 不提供同总额，才考虑复用现有 accession structured-fact adapter 补充原生候选及其原来源；本次未读取 Company Facts 证明总额是否在其候选中，不能承诺仅靠过滤必然完成动态运行。

接口上的意图可表达为：

```text
native_reports = existing_native_income_reader(exact_originals)
scope_evidence = existing_table_binding(native_reports, full_revenue_section)
eligible_facts = existing_facts whose reported revenue scope is proven complete
result = existing_calculator(existing_B01_spec, eligible_facts)
verify existing amount/context checks + selected revenue scope evidence
```

`eligible_facts` 是原件范围准入，并不另写金额选择、排序或计算引擎。判不清时保存具体未证明点并区分开发缺口/披露冲突，不能以“有两个同金额”继续通过，也不能把本例已有总额写成披露不足。

### 已有函数能复用，但不能误称现成覆盖

- `_InlineTableIndex`（financial_structured.py:36-110）和 `_fact_cells`（168-189）：事实 ordinal → 唯一原表格单元格，检查 stream 数量和 raw cell 对应。
- `_cell_proof`（financial_duration.py:89-93）：可审查的行/列/跨列/原文本证据。
- `_ReportedFactMetadata`、`_verified_context`、`_source_value`：已有 native fact/context/单位/scale 的读取与验证。
- `precision_choice`（r5_b06_scope.py:16-31）：同量的精度/舍入一致性；不能跨范围比较后宣布相同。
- `index_source_structure` 与关联脚注/原表声明机制可提供表前说明和必要范围限定；financial_structured 的 `_revenue_column`（192-219）专用于现有银行收入列语义，不能原样套到本工业收入行。
- `_scale` 当前只接受 `in millions` 等格式；本原表裸 `(MILLIONS, EXCEPT PER SHARE DATA)` 不在该语法中。`_column_period` 对年份所在行的其他单元格也只识别其既有表头描述，不能静态宣称裸 MILLIONS 单位头可通过。因此正向验收必须覆盖这个真实表头，复用 native USD/scale/期间而非绕过它们；确有必要时对既有表头解析做有界适配。不要为修范围再复制一套单位/期间 resolver。

## 业务含义边界

按本委托已明确的 B01 全收入目标，选取原申报已报告 Total revenues 属于既定含义的正确性修复；不需要把合作收入重新分类，也不需要新增供应链、审计或隐性债务分析。

但不能假装冻结 Spec 已写有完整的机器 total-scope 条件。其 `legacy_companyfacts_v1` 和 concept 顺序有历史合同含义，specs.py:244-253 也拒绝改其冻结语义。实施应作为显式后继来源范围准入，更新实际消费者处理绑定，生成新 Result，保留旧 Spec/Run/失败。全局把 Revenues 排第一会改变所有布局的选择，且 Revenues 标签也不能单独保证完整；这是不充分的修法。

如果另行要求把 royalty 从 Other income 纳入某期间、使用后年重列前期代替原期间、改变税口径、净额/总额或年度主体范围，那是新的业务/期间含义决策，超出本次。Pfizer FY2024 原件的 FY2023 重列数 59,553m 不能替换本次 FY2023 申报的 58,496m。

## 后续验收应包含的明确正反例

| 类型 | 输入/情境 | 必需行为 |
|---|---|---|
| 正向真实原件 | 本 table_000113：50,914 产品 + 7,582 合作，报告总额 58,496；两原件一致 | 新 B01 自动产出 58,496m；保留总额及分量范围证据，无人工指定单元格/数值 |
| 负向实际反例 | 50,914 的同 concept primary/XML 金额、context、USD 全通过 | 不取得 B01 全收入接受；明确是 subtotal scope，不伪装缺失 |
| 正向回归 | 客户合同收入本身在完整收入区段即全收入，没有另列应包含分量 | 保留该 concept 和原金额；不得因标签是客户收入一律拒绝 |
| 负向范围 | 同总額/标签出现在分部、地域、预测、另一公司或其他期间 | 不只凭 total 字样/最大值接受；检查原生主体、期间、完整范围及关联说明 |
| 负向冲突 | 同范围同精度总额互异、组件关系与报告总额矛盾或单位不一致 | 保存具体冲突，继续不受影响指标；不猜数、不以 precision_choice 消除范围矛盾 |
| 负向历史角色 | FY2024 报表中 FY2023 重列 59,553 被拿来覆盖本原申报 | 拒绝错期间角色；保留 58,496 的本申报来源身份 |
| 接入回归 | historical B01、ordinary continuous B01、successor B01、B03 的 B01 依赖 | 使用同一范围证明与原事实准入；不会某条路径绕过或依赖使用旧 subtotal |

本轮没有开发源码/tests、没有运行单元测试/公司指标/模型、没有 commit/push、没有网络/SEC/provider/paid 调用、没有改 peer source-inputs 或账本。测试状态为 **静态诊断 + 原件 hash/标签/XML 金额核对；公共函数运行验证 NOT_RUN**。现有 selected_income_source_v1 单测名称覆盖身份、namespace、USD、期间和短期间可见冲突，没有看到收入总额/分量用例；不以现有测试通过代替这项新验收。

操作上限执行：9 次 functions.exec 包装及 9 次 exec_command（按含嵌套计 18 个工具调用）；常规消息 2 条含 final；只写本目录 conclusion.md 和 raw-check.json。本诊断不是修复交付、正式 Run、Ready、merge、发布或 active 证据。

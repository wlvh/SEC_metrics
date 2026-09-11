# B06 独立来源与规则调查（实施前）

审阅者：Codex 独立子任务 `/root/b06_source_audit`（模型审阅，非人工批准）。只读本地仓库与保存 SEC 原文；未读取旧矩阵用于选择答案，未执行 provider/paid/SEC、未执行旧 B06 生产函数，未运行新原生结果验证。

## 结论

十家公司都有本地保存的最新 ordinary 10-K submissions 与 Company Facts；十份 Company Facts 文件字节均与已存 headers.json 的 sha256 一致。本报告按 latest saved recent ordinary 10-K → exact accession + actual reportDate + instant facts 查询，保存完整候选概念及原始 fact 对象。材料存在和 hash 对上不等于已满足新的原生生产/发布许可。

现有 catalog/metrics/B06_debt_to_equity.md 的类型为 direct_numeric、source_mode=structured_first_ai_fallback、entity_scope=consolidated、forbidden_confusions=[Ford Credit,captive finance]。来源策略只允许 STRUCTURED_SOURCE_AMBIGUOUS 启动既定 fallback。本轮零模型预算，因此不能把 fallback 当成功或最终缺失。所有十家公司按现有 applicability all=[]/none=[] 均无结构性不适用依据。

定义文档分三层：直接总额（不加 adder）；同族 current+noncurrent（不跨族）；无总额/完整pair后才进入短期借款补充和受限 standalone 分支。equity<=0 不输出普通比值。仅靠第一个能匹配的 branch，缺少覆盖冲突的检查，会漏过真实业务错误。

## 原始材料中的分支与缺口

| 公司 | 实际时点 | 原文 debt 候选（USD bn，非接受结果） | StockholdersEquity（USD bn） | 独立判断 |
|---|---|---|---|---|
| Marriott | 2025-12-31 | DebtAndCapitalLeaseObligations=16.204 | -3.771 | 非正权益，不能普通ratio |
| Southwest | 2025-12-31 | LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities=4.919 | 7.981 | 直接分支真实正例候选；保留同份材料LongTermDebt=4.929及finance leases=0.078，解释定义边界，不强加相加 |
| Ford | 2025-12-31 | Company Facts只有 finance lease pair=0.890 | 35.952 | lease-only不代表total debt；instance确有工业/FordCredit维度，需scope复核 |
| Pfizer | 2025-12-31 | LongTermDebtCurrent 2.997 + Noncurrent 61.641 =64.638 | 86.476 | 同族正例候选；另有OtherShortTermBorrowings0.157，需明确已有规则不加adder的覆盖含义 |
| JPM | 2025-12-31 | 长期债务含到期435.206；另有ShortTermBorrowings64.776 | 362.438 | “长期含当期到期”并不等于所有短期债务，不能自动加也不能掩盖缺口 |
| Salesforce | 2026-01-31 | LongTermDebtCurrent4 + Noncurrent10.439=14.439 | 59.142 | 同族正例候选；finance lease0.535另存，规则必须明确是否已含/排除，不能随意加 |
| Lumen | 2025-12-31 | DebtAndCapitalLeaseObligations17.441；另一Tier1含到期17.815 | -1.117 | 两总额不同+非正权益，必须保留冲突与非正权益原因 |
| Macy's | 2026-01-31 | standalone LongTermDebtAndCapitalLeaseObligations2.432；lease pair0.013 | 4.860 | standalone定义为noncurrent，不可盲称total-like；lease-only不应抢先成功 |
| Paramount successor | 2025-12-31 | DebtAndCapitalLeaseObligations13.658 | 11.693 | 当前主体instant比例可调查；不可跨predecessor混合，NCI-inclusive equity12.887不能自动代换 |
| Enphase | 2025-12-31 | LongTermDebtCurrent0.632183 + Noncurrent0.572194=1.204377 | 1.087023 | 同族、同份申报、同单位和时点的主路径正例候选 |

这张表不声称上述候选全部应输出成功。重要区别是“数值与原始fact一致”与“该组概念足以代表总债务”各自必须成立。

## Ford 原始 instance

本地 `evidence/accession_materials/ford_motor_company_37996_000003799626000015/f-20251231_htm.xml` 的 actual instant=2025-12-31：

- CompanyExcludingFordCreditMember：LongTermDebtCurrent=5.550bn；LongTermDebtNoncurrent=16.369bn。
- FordCreditMember：DebtCurrent=51.752bn；LongTermDebtNoncurrent=89.665bn。
- 存在更细 unsecured/asset-backed 维度，不能把这些加总后再次加总父级。
- Company Facts flat standard facts 的 finance lease pair0.890bn显然不是上述任何完整债务口径。

工业债务定位可证明，不意味着35.952bn集团equity就能当工业分母。当前Spec要求consolidated、禁止FordCredit/captive finance混淆，而业务说明主矩阵更偏工业口径；应在新声明式草案中明确此次范围，证据不足就保留NEEDS_REVIEW，不能默默重定义。

## 最小未决经济含义

1. 总额优先意味着禁止重复加数，不意味着无视已证明不包含的其他债务。JPM为最明显真实例子。既有定义将长期含到期列为Tier1；此次不能擅自扩大加法，但应明确覆盖不足时是待复核。
2. FinanceLeaseLiability current/noncurrent是一类债务子集。完整同族pair只证明该子集的流动/非流动齐全，不证明total debt齐全。
3. standalone LongTermDebtAndCapitalLeaseObligations 的保存SEC描述明确 `classified as noncurrent`，与旧文档“total-like base”不是天然同义。Macy's提供真实冲突，不能仅依命名猜测。
4. 多个直接总额候选冲突（Lumen）应保存每个候选和排除/待复核原因。先选一个数值再因负equity停止，也不能丢掉冲突事实。
5. Equity优先StockholdersEquity，NCI-inclusive不应无依据替换；单位/主体/实际instant相同仍需原生验证。

以上均有独立原始来源证据；不建议为追求完成率降低门禁。可以先完成无争议主路径，把其余明确列作结构化歧义/范围复核，保持fallback责任。

## 可复用的现有职责

- `deterministic_router.adapt_companyfacts`：原字节/SourceReference绑定、实体CIK、概念白名单、instant facts →原生DeterministicVerifiedClaim；保留fact id/accession/entity/period/unit。
- `sources.companyfacts_structured_facts`：生产级CompanyFacts解析；不能由旧矩阵反推期间。
- `zero_ai_r2._select_component_claim` / `_select_deterministic_branch`：现有同申报/期末/单位选择和候选拒绝理由；当前是first complete branch，不自动证明B06债务覆盖充分。
- `zero_ai_r2._formula_value`已有ratio，但B06 sum-then-ratio和非正权益应以受控声明式规则接入；不能通用Calculator硬编码metricID。
- `_compiled_deterministic_spec` / `_deterministic_metric_graph` / structured_observation / calculate_observation_metric 提供claim→observation→result/trace基础。
- R2 catalog及release集合冻结于既有22指标，不应直接原地加入B06或修改R2常量；当前B06 table Spec本身不构成结构化公式与新增迁移许可。
- Ford `parse_accession_xbrl_source` 可解析现有原始instance dimensions，仅为范围证据；本轮不能因此擅自改B06 source strategy或运行AI fallback。

## 执行范围与证据索引

亲自执行：本地JSON/XML解析、精确accession/instant选取、10份CompanyFacts/headerSHA核对、Ford dimensions抽样和代码接口读取。
未执行：新Run/Review/Calculator图重放、新完整候选验证、发布链、任何业务网络或GitHub写入。原生接受与独立结果最终审核待实现交付后单独进行。

- raw-source-census.json：十家公司完整所选申报、源路径与文件SHA、候选描述及原始facts。
- ford-instance-census.json：真实Ford完整instance源SHA及debt/equity维度事实。
- source-header-checks.json：10份原文与保存header哈希、snapshot时间核对。

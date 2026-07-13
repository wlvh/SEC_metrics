# 05｜SEC_metrics 项目全景与专家指南

**用途**：让项目负责人、审计者、开发者完整掌握 SEC_metrics spike 的目标、架构、计算逻辑、证据链、准确性防线、验收方法、扩展路径和专家复核边界。  

---

## 目录

1. 可信度声明与当前状态
2. 项目边界与交付物实况
3. SEC 数据平面与 XBRL 基础
4. 架构总览：流水线、配置、抽取器
5. 指标计算通路：STD_XBRL、DIM_XBRL、MDA、DEF14A、8-K
6. 准确性防线：证据链、golden、validation、unittest
7. 风险登记簿：已关闭项与仍开放项
8. 从第 11 家到第 1000 家公司的扩展方法
9. 输出文件怎么读
10. 如何人工审计一个指标
11. 常见错误模式与定位方式
12. 轻量包与完整包的验收方法
13. 生产化路线图
14. 专家训练清单与快速命令
15. 术语表与五轮演化史

---

## 0. 这份文档的可信度声明（先读这一节）

当前 verdict 必须分成两层：

| 验收对象 | 当前结论 | 原因 |
|---|---|---|
| 去公司特例化 + 轻量审核硬化 | ACCEPT WITH CAVEATS | 公司名业务派发已清零，profile / extractor / concept probe 架构已建立；Basel threshold 和 light golden 循环自证已修。 |
| scale-ready 生产化 | 部分完成，仍需 live 试点 | scale route、10-K/A fallback、Basel threshold、captive finance 等旧风险已关闭；仍需处理 FI SIC 覆盖、住宿表格召回、新金额类维度事实断言，并用 Hilton / Citi / GM / ServiceNow 这类真实第 11 家试点跑全流程。 |

本文档合并后采用三级可信度标记：

```text
[实测]   已执行代码或对抗测试，有运行结果为证
[考证]   已读实现原文，逐行确认过逻辑
[声明]   来自报告或历史文档的声明，未在本轮独立复验
```

全文未显式标注处默认为 [考证] 级；涉及当前输出统计、门禁结果、包内文件列表的断言优先按当前工作区实测结果更新。


## 1. 项目是什么：一句话、边界与交付物实况

**一句话**：直接连接 SEC（美国证券交易委员会）官方数据端点，对 10 家不同行业的美国上市公司，计算最近一个已申报财年的财务、治理、风险与事件指标，输出每个数值都可追溯到 SEC 原始响应的指标矩阵。

**任务性质**是一次 spike——工程术语，指为验证可行性而做的一次性探索开发，不是生产系统。它的成功标准写在 01 号 SOP 里且值得背下来：**不是"所有指标都有数值"，而是每家公司 × 每个指标都有 value / status / formula / source / evidence / confidence 六件套**。找不到数据时诚实标状态是合法结果；为填满矩阵而猜数是失败。这条价值观贯穿了后面所有的机制设计。

**终版交付物实况**（[实测]，直接统计自 round3 包）：

```text
指标矩阵      230 行 = 10 家公司 × 22~27 个指标
有数值的格    161 个，空值 69 个；有值格全部带证据链
状态分布      OK 73 | TEXT_QUAL 50 | NOT_AVAILABLE_SEC 31 | 8K_ITEM_OK 30
              DIM_XBRL_OK 12 | DEF14A_OK 8 | NOT_EXTRACTED 5
              NOT_MEANINGFUL 10 | MDA_OK 6 | NEEDS_REVIEW 2
              OK_APPROX 2 | N_A_STRUCTURAL 1
来源分布      8K事件 60 | 派生计算 48 | 标准XBRL 27 | 维度XBRL 12 | 委托书 8 | MD&A 6
验证体系      63 条 golden 断言 + 75 项 repair validation + 17 个 unittest 回归测试
              + 泛化扫描器 + 分层抽样复审 + 第 11 家公司行为夹具
代码规模      sec_pipeline.py 单体约 14,000 行 + 13 个编号阶段脚本（各约 20 行薄封装）
              + sec_http.py / sec_urls.py + tools/ + tests/
```

10 家公司的挑选本身是实验设计：Enphase（干净标准 XBRL，当数值基准种子）、Ford（负营业利润 + 专属金融子公司 + 非常规 capex 标签，专门踩坑）、JPMorgan（银行，整套指标体系都不同）、Salesforce（1月底财年 + SaaS 指标）、Marriott（KPI 藏在 MD&A 表格里）、Paramount（财年中途换报告主体）、Macy's（2月初财年）等——每家都代表一类扩展到千家公司时必然遇到的结构性难题。

---

## 2. 数据从哪来：SEC 的三个数据平面与 XBRL 速成课

要看懂本项目，必须先建立 SEC 数据的心智模型。SEC 对外提供的机器可读数据分三个平面，本项目按"companyfacts 优先、accession 补足"的策略组合使用：

### 2.1 三个数据平面

**平面一：submissions（申报索引）**。`https://data.sec.gov/submissions/CIK##########.json`。回答"这家公司交过什么文件"：每份申报的表单类型（10-K 年报、10-Q 季报、8-K 重大事项、DEF 14A 委托书……）、accession 号（申报的唯一编号，格式如 `0001463101-26-000013`）、申报日、报告期末日。同时携带公司元数据：正式名称、曾用名、SIC 行业码、财年末（fiscalYearEnd，如 `1231`、`0131`）、实体类型。本项目的 M0/M1 阶段全靠它。

**平面二：companyfacts（公司级标准事实聚合）**。`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`。SEC 把一家公司历年申报中所有**标准分类账、公司整体层面**的 XBRL 事实聚合成一个 JSON：营收、净利、总资产、现金……每条事实带概念名、单位、期间、来源 accession、申报日。它的致命局限：**不含维度事实**（比如"按 Basel 标准法口径的 CET1 比率"这种带轴/成员标注的数据）和公司自定义概念。这就是本项目必须有平面三的原因。

**平面三：accession materials（原始申报材料）**。`https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/...`。每份申报的原始文件目录，本项目消费其中四类：`index.json`（目录清单）、`{accession}.hdr.sgml`（申报头文件，含 8-K 的 `<ITEMS>` 项目编号列表——这是事件信号的数据源）、`FilingSummary.xml`（文件角色说明）、以及 **iXBRL instance**（内联 XBRL 的主文档，见下）。

### 2.2 XBRL 五分钟速成（本项目的核心词汇全在这里）

XBRL（eXtensible Business Reporting Language）是把财务数字变成机器可读标签的标准。iXBRL（inline XBRL）是它的现代形态：标签直接嵌在人类阅读的 HTML 年报正文里，同一份文件人机两用。

- **concept（概念/标签）**：一个数字的语义名字，如 `RevenueFromContractWithCustomerExcludingAssessedTax`。分两类：**标准概念**属于 us-gaap 分类账（namespace 是 `fasb.org/us-gaap/...`，全市场通用）；**公司扩展**是公司自造的标签（namespace 是公司域名，如 JPM 自造的 `CommonEquityTier1CapitaltoRiskWeightedAssets`——注意那个不合规范的小写 to）。**同一个经济事实，不同公司可能用不同标签**，这是候选链机制存在的根本原因。
- **context（上下文）**：数字属于哪个期间、哪个报告主体、带什么维度。
- **dimension（维度）= axis（轴）+ member（成员）**：给事实加限定。例如 `us-gaap:RiskWeightedAssetsCalculationMethodologyAxis = jpm:BaselIIIStandardizedMember` 表示"这个资本比率是按 Basel III 标准法算的"。轴通常是标准的，成员经常是公司自造的——这个不对称是泛化设计的关键约束。
- **unit（单位）**：`iso4217:USD` 是美元金额，`pure` 是纯数（比率）。
- **scale（缩放属性）**：iXBRL 数字标签可声明 10 的幂缩放（正文显示 294,804 百万，标签值 294804 + scale=6）。

### 2.3 HTTP 访问纪律

[考证+实测] `sec_http.py` 实现：所有请求带 `User-Agent: <组织> <邮箱>`（SEC 硬性要求，缺失会 403）；全局限速 ≤5 请求/秒（sleep 节流）；403/429/5xx 指数退避重试；每次请求写入 `evidence/requests_log.csv`；原始响应落盘。当前工作区 `evidence/requests_log.csv` 有 859 条请求记录，域名仍只有 **www.sec.gov 和 data.sec.gov** 两个域名，零第三方数据源。

---

## 3. 架构总览：单体、流水线与知识安置三原则

### 3.1 物理形态：一个单体 + 十三个薄封装

全部逻辑住在 `scripts/sec_pipeline.py`（约 14,000 行）这一个单体模块里；`00_smoke_test_sec_access.py` 到 `12_validate_repair.py` 十三个编号脚本各约 20 行，只做一件事：`run_stage(stage_name="...")`。调度表在单体尾部的 `STAGES` 字典。这个形态是 spike 阶段的务实选择，产品化时应拆分——但拆分时**必须保留的**是下面的逻辑架构。

### 3.2 流水线：M0–M7 的数据流

```text
M0 身份解析     company_tickers + submissions ──> company_resolution.csv
M1 定位申报     submissions ──> latest_filings_inventory.csv
                （target 10-K / prior 10-K / DEF 14A / 财年窗口内全部 8-K）
M2 标准指标     companyfacts JSON ──> concept_inventory + 选择算法 ──> 标准/派生指标
M3 维度事实     accession 的 iXBRL instance 流式解析 ──> {company}_instance.csv
                ──> Basel/RPO/AuditorName 等解析器消费
M4 事件信号     每份 8-K 的 hdr.sgml ──> <ITEMS> 解析 ──> events.csv
M5 治理薪酬     DEF 14A 的 ecd 分类账事实 ──> C03 薪酬 / C02 董事会
M6 文本 KPI     MD&A 文本 ──> 表格机（住宿业 KPI）+ 风险法律文本信号
M7 组装验收     metrics_matrix + coverage + golden 断言 + 报告 + verdict
```

每阶段的输出既是下一阶段的输入，也是独立可审计的中间产物——这个"每层落盘"的设计让Agent能在任意断面重算验证。

### 3.3 知识安置三原则（本项目最重要的架构思想）

千家公司扩展性的核心不是某个函数，而是一条纪律：**公司身份（名字、CIK）只允许住在三个地方——输入配置、测试夹具、异常台账；业务逻辑的每个分支必须以可观测属性为键**。这条纪律有机器门禁保障（`tools/check_no_company_literals.py`，AST 级扫描全部代码常量，[实测] 注入探针 6 种违规形态抓获 5 种）。属性分三级，构成派发阶梯：

```text
第一级 登记属性   来自 submissions：SIC 行业码、财年末、实体类型、曾用名
                  用途：决定"哪些指标适用于谁"
第二级 能力探针   来自申报文件本身："instance 里存在概念 X / 轴 Y / 成员模式 Z 吗？"
                  用途：决定"用哪条抽取策略"。问数据而不是认名字。
第三级 词法配置   人工行业知识的数据化居所：KPI 词表、量纲区间、口径优先序
                  用途：让人工判断以数据形态存在，而非控制流形态
```

具体落地：`config/company_registry.csv` 承载全部个体信息（逐列语义见第 7 节）；`config/metric_applicability.yaml` 以**行业 profile** 为键定义每个 profile 挂载哪些抽取器（`lodging → LodgingKpiExtractor`，`financial_institution → BaselCapitalRatioExtractor`……），并含 `profile_rules`（SIC 区间到 profile 的自动推导规则）与 `settings`（量纲区间、scope 优先序等词法配置）；业务代码通过 `has_extractor(extractors, "XxxExtractor")` 这样的**能力查询**派发，抽取器类本身是空的标记类（capability tag）。[实测] 折叠字符串拼接后的全库扫描，业务代码中公司身份引用为**零**。

---

### 3.4 通用性不是目标：正确性与工程量的适配治理

本项目把“公司特例”赶出生产控制流，这是必要的，但不能误解成“越通用越好”。真正目标是**足够正确**和**工程量可控**；通用性只是同时服务这两个目标的手段。当通用性开始牺牲正确性，或者为了覆盖所有可能命名而写出更复杂、更脆弱的解析器，它就从资产变成负债。

合理适配分五层：

```text
第 0 层：不可妥协的通用骨架
  SEC-only、证据链、period 选择、status 语义、golden/validation、请求日志。

第 1 层：指标级通用逻辑
  companyfacts 选择算法、RPO 标准概念、AuditorName、ecd:PeoTotalCompAmt。
  SEC/XBRL 已给结构化事实时，优先使用，不写文本正则。

第 2 层：行业/业务模式级适配
  金融机构 Basel、住宿业 RevPAR、SaaS/合同履约 RPO、制造业 captive finance。
  合法，因为同一行业共享披露习惯、单位和不变量。

第 3 层：配置级公司事实
  CIK、fiscalYearEnd、successor/predecessor、related_ciks、roles、人工 override。
  这些可以按公司写入 registry，因为它们是输入事实，不是计算逻辑。

第 4 层：受控公司补丁（默认禁止，但不是永远禁止）
  只有在高价值公司、公开披露形态确实独特、行业抽象代价过高时才允许。
  条件是：隔离成 data/config 或 adapter；有 evidence；有 regression；
  exceptions/docs 写明理由；有迁移或过期条件；不得污染主路径。
```

Basel 资本比率解析器是反面教材：从 JPM 私有概念出发追求“泛化”，一度写出过宽的概念匹配器，导致监管最低要求可能赢过实际资本比率。正确做法不是回到 `if company == "JPM"`，也不是写无限宽的语义正则，而是**正负词表 + 标准轴锚定 + 候选角色分离 + 行为级 fixture**。好的泛化不是“能匹配更多字符串”，而是“知道哪些字符串绝不能成为主值”。

扩展到上千家公司时，应按行业簇推进：每一簇先选 3–5 家真实公司做 live pilot，抽取器以**高精度优先**；抽不到时宁可 `NOT_EXTRACTED` / `NEEDS_REVIEW`，不要让泛化器产生伪 OK 数值。等同一失败模式重复出现，再提升为行业规则或标准 extractor。

---

## 4. 数字是怎么算出来的：五条数据通路逐一拆解

矩阵里 161 个有值格来自五条通路，每条的机制、防错设计和已知边界如下。

### 4.1 通路一：STD_XBRL 标准指标 + DERIVED 派生（69 格，营收/净利/资产/现金流等）

**选择算法**（02 号定义文档锁定，[实测]   用完全独立的实现重算过 Enphase/Ford 全部数值并与 live SEC 对账吻合）：

```text
期间型（营收、净利、现金流）:
  form 以 10-K 开头
  AND end == 目标财年末
  AND 有 start 且 duration ∈ [300, 400] 天
  多条命中时取 filed 最新者
时点型（资产、负债、现金）:
  同上，但要求无 start（instant 型）
上年值: 同一算法，end 换上一财年末
```

300–400 天这个 duration 窗是防错核心之一：它自动拒绝季度事实、也自动拒绝**存续残段**（stub period，指公司财年中途成立/重组导致的不足一年的报告期——Paramount 的 successor 实体只有 2025-08-08 起的 5 个月事实，这个过滤器正确地拒绝了"把 5 个月当全年"的错误）。

**候选链机制**：因为不同公司给同一经济事实贴不同标签，每个指标定义一条按优先级排列的概念链，逐个探测取首个命中，且**实际命中的标签必须记录进证据**。例如营收链：

```text
RevenueFromContractWithCustomerExcludingAssessedTax → Revenues
  → SalesRevenueNet → RevenueFromContractWithCustomerIncludingAssessedTax
```

真实世界的必要性证据（[实测]）：Marriott/Pfizer 回退命中 `Revenues`；Ford 的 capex 命中链尾的 `PaymentsToAcquireProductiveAssets`——live SEC 确认 Ford 的 companyfacts 里**根本不存在**链首的常规概念；Ford 净利命中 `ProfitLoss`（含少数股东权益口径，已在 notes 透明标注）。

**派生公式与口径纪律**（44 格）：

```text
EBITDA proxy      = 营业利润 + 折旧摊销（明确不加回减值，命名为 GAAP proxy）
自由现金流 FCF     = 经营现金流 − capex
负债权益比 D/E     = 总债务 / 股东权益
                    总债务 = LongTermDebt（或 Current+Noncurrent 二选一防重复）
                            + 短期借款 + 商业票据 + 融资租赁负债
                    硬性排除 DebtSecurities*（那是投资资产不是借款）
利息覆盖倍数       营业利润 ≤ 0 时强制 NOT_MEANINGFUL（Ford/Lumen 亏损年，
                    输出一个负倍数只会误导）
流动比率           银行结构性不适用 → JPM 标 N_A_STRUCTURAL
                    （[实测] G2 断言故意请求 JPM 的 AssetsCurrent 端点确认 404，
                    把"银行没有流动资产科目"这个事实固化为机器证据）
```

### 4.2 通路二：DIM_XBRL 维度指标（12 格：JPM 资本比率 ×2 + 全体 AuditorName ×10）

这条通路消费 M3 流式解析出的 instance inventory（每公司数千条事实，含完整维度）。三个解析器：

**Basel 资本比率解析器**（A01 Tier 1 比率 / A02 CET1 比率）。这是全项目迭代次数最多的组件，终版决策树（[实测] 六向对抗测试）：

```text
候选资格 = unit 为 pure
         AND period_end 匹配
         AND 维度含标准轴 RiskWeightedAssetsCalculationMethodologyAxis
         AND NOT 阈值概念（规范化名含 minimum / requiredforcapitaladequacy /
             requiredtobewellcapitalized / wellcapitalizedminimum /
             tobewellcapitalized / capitaladequacyminimum 之一即拒绝）
         AND 语义匹配：
             规范化 = 小写去符号，且 tierone 统一替换为 tier1
             含 riskweightedassets 或 riskbasedcapitalratio 之一
             A02 要求含 commonequitytier1 或 cet1
             A01 要求含 tier1 且非 CET1（防 CET1 被错归 Tier 1）
选择排序 = ParentCompanyMember/合并口径优先 > Standardized 优先
         > 无 LegalEntityAxis 优先 > context 字典序
```

三条设计原理值得记住：**(a)** 锚定在标准轴而非成员——各银行的成员名各不相同（`jpm:BaselIIIStandardizedMember` vs 其他行的自造名）但轴是 us-gaap 标准的；**(b)** tierone→tier1 统一——us-gaap 官方命名用拼写式 TierOne，JPM 扩展用数字式 Tier1，不统一就会漏配标准命名（这是第三轮修掉的真 bug，[实测] 拼写式 CET1 曾被错分类为 A01）；**(c)** 阈值排除——银行 10-K 同时标注实际比率和**监管最低要求**（及格线 7.0%、well-capitalized 线 6.5%），两者单位维度期间全同，不做词法排除的话监管及格线可能被选为银行的实际比率（[实测] 第四轮曾用同维度对决打穿过，终版候选池阶段即剔除）。被排除的阈值事实**不丢弃**，移入 `basel_ratio_candidates.csv` 带 `candidate_role=regulatory_threshold` 标注——它们是有价值的上下文（实际比率距及格线的距离就是资本缓冲）。终版 JPM 输出：A01=0.155、A02=0.146（母公司合并口径，Basel 口径在 notes 注明）。

**RPO 解析器**（B12，Salesforce 的合同剩余履约义务）。RPO 是 ASC 606（现行收入确认准则）强制披露项，`us-gaap:RevenueRemainingPerformanceObligation` 是标准概念——这意味着该指标对**全市场任何公司**零个体代码可得。解析器：概念精确/后缀匹配（兼容公司前缀扩展）+ 排除 timing 轴概念 + USD 单位 + 优先总额型事实、退而求其次将 current+noncurrent 分量加总。[实测] Salesforce 总 RPO=724 亿 = 流动 351 亿 + 非流动 373 亿，内部自洽。历史教训：第一代实现是烧死了 "as of January 31, 2026" 日期字符串的文本正则，费力重造了结构化数据里现成的数字——**结构化 inventory 有的概念，禁止文本正则**，这条已固化为验证门禁。

**AuditorName 对照器**（C04，审计师轮换信号）。`dei:AuditorName` 是每份 10-K 强制标注的标准事实。双路径：8-K item 4.01（审计师变更专用事项）扫描 + 本年/上年 10-K instance 的 AuditorName 对照。10 家全部走通 DIM_XBRL_OK。

### 4.3 通路三：MDA 文本 KPI（2 格：Marriott 入住率与 RevPAR）

这是全项目技术上最精巧的组件，因为它要在**没有结构化标签的自由文本表格**里可靠取数。RevPAR（每间可售房收入）、ADR（平均房价）、occupancy（入住率）是酒店业三大 KPI，只出现在 MD&A 的运营统计表里。终版流水线（[实测] 四组合成表格对抗）：

```text
1 分段     按 KPI 关键词把正文切成 5000 字符的表格候选段
2 表头映射  在段内找 RevPAR / Occupancy / ADR 表头的首次出现位置，
           按位置排序推导列序（真·表头驱动，非位置假设）
           + 全排列作为兜底候选
3 行锚定   按配置的口径优先序找行标签：
           comparable systemwide worldwide > systemwide worldwide
           > companywide > worldwide（脚注号 (2) 作为被容忍的可选模式，
           不再是锚点——第一代实现把正则锚在脚注编号上，是反面教材）
4 装配     行内数字按"绝对值/变化值"交替节奏取偶数位，按候选列序指派
5 恒等式   RevPAR = ADR × Occupancy / 100 必须成立（误差 ≤5%）
           ——既是硬门（不满足即弃该候选）又是排序键（多候选取误差最小者）
6 量纲区间  RevPAR ∈ [30,600] USD、occupancy ∈ [0,100]%（配置化）
```

第 5 步是点睛之笔：三个数字的哪种指派满足行业恒等式，哪种就是真列序——**用行业代数不变量做列序自识别**，比任何排版假设都稳。[实测]：Marriott 列序（RevPAR 前置）与 Hilton 惯用列序（Occupancy 前置）都被正确解出且恒等式误差 0.02%；三年度对比表（节奏不符）和"RevPAR increased 2.0%"这类增长率句子（第一轮事故的原型）都诚实空手而归——错误节奏的失败模式被恒等式压制成**召回损失而非错值**，这个失败等级排序是对的。证据 quote 同时携带 `raw_header= / raw_row= / parsed= / identity_error=` 四段，原文性与可复核性兼备。

### 4.4 通路四：DEF14A 治理（8 格：CEO 薪酬）

ecd 是 SEC pay-versus-performance 规则强制所有申报人在委托书（DEF 14A）中使用的高管薪酬 XBRL 分类账。C03 直接消费 `ecd:PeoTotalCompAmt`（PEO=principal executive officer，即 CEO）：遍历全部公司、统一概念过滤、USD 单位、目标财年期末——**零身份键，天然泛化**。8 家命中（JPM $40.6M、Salesforce $49.4M……）；Marriott/Paramount 的委托书 ecd 无此概念，诚实标 NOT_EXTRACTED。多 PEO（联席 CEO / 年中换任）场景：明细全部进 governance_signals，主矩阵不做求和（多个人的薪酬加成一个"CEO 薪酬"是语义错误）。历史教训：第一代实现抓的是文本正则误配的无意义小数（66、196……），而正确答案就躺在自己 dump 的 ecd inventory 里没被消费——"最后一公里消费失败"这个模式由此得名，并催生了"inventory 优先"门禁。

### 4.5 通路五：8-K 事件信号（60 格）

8-K 是重大事项即时申报，每份的 hdr.sgml 头文件里有 `<ITEMS>` 标签列出事项编号（5.02=高管变动、4.01=审计师变更、4.02=财报重述、1.03=破产、1.01=重大合同、2.01/8.01=并购相关）。M4 对财年窗口内全部 8-K（终版约 326 条事件、125 份多事项申报正确拆行）解析编号并映射到 C01/E01–E05。设计要点：E01 并购不能只靠 8.01（那是"其他事项"杂项），需正文关键词确认；E02 破产计数为零时报告明写"零是正常结果"——**零值的语义必须显式声明**，否则读者分不清"没发生"和"没查"。

### 4.6 状态枚举：这套系统的合同语言

13 个状态不是装饰，是下游消费的语义合同。最易混淆的四个，用血泪案例区分：

```text
NOT_AVAILABLE_SEC   SEC 申报中确实不存在该数据。
                    例：Pfizer 利润表不呈报营业利润小计，OperatingIncomeLoss
                    概念在其 companyfacts 中根本不存在（[实测] 验证过）。
NOT_EXTRACTED       数据可能在文本/表格里，但本轮未能可靠抽取。
                    诚实的能力边界声明，不是数据不存在。
NOT_MEANINGFUL      结构上无意义。例：亏损年的利息覆盖倍数；
                    Paramount 换主体年的同比增速（残段期 vs 全年不可比）。
N_A_STRUCTURAL      行业结构性不适用。例：银行没有流动资产/流动负债科目。
```

历史教训：第一代曾把"successor 只有残段事实"标成 NOT_AVAILABLE_SEC（数据明明披露了，只是口径不匹配）、把"AuditorName 躺在 inventory 里没消费"标成 NOT_AVAILABLE_SEC——**状态语义污染会让下游把"没做完"当成"世界上不存在"**，这是比错数值更隐蔽的毒。

---

## 5. 准确性靠什么保证：五层防线 + 一条守恒律

### 5.1 防线一：证据链强制

每个数值必须具备三件套：accession（哪份申报）+ concept_or_section（哪个概念/章节）+ context_or_dimension（哪个上下文/维度），文本类另加原文 quote。**quote 必须支撑 value**——这句话看似废话，却是第一轮最大事故的墓志铭：当时 Marriott RevPAR=2.0 挂着 MDA_OK 状态，证据 quote 是一段讲分时度假的无关文字（2.0 是正则从 "RevPAR increased 2.0%" 里误抓的增长率）。由此确立的元规则：**错值戴 OK 状态比取不到危险一个量级**——取不到是显性缺口，错值是隐性毒药。

### 5.2 防线二：Golden 断言体系（63 条）

Golden 断言是"代码跑通但数字错"的专用解毒剂：对两家基准公司（Enphase=干净标准 XBRL、Ford=专门踩坑）的全部核心数值，由人工事先从原始年报核出**锁定期望值**（存于 `tests/fixtures/sec_10_company_spike/golden_expected_values.csv`），管道必须独立复现出完全相同的数字。分四组：G1 结构断言（10 家 CIK/财年末）、G2 防误用断言（故意确认 JPM 无流动资产端点、Ford 无常规 capex 概念——**把"预期中的缺失"也固化为断言**，防止未来有人"好心修复"）、G3/G4 数值断言（Enphase 13 值 + Ford 11 值，含派生量和命中标签断言）、G5 候选值（其余 8 家 × 3 值供人工核对）。铁律：**断言失败即停机报告实际值，不得修改期望值，不得硬编码绕过**。独立性论证：断言与计算共享选择函数（同一单体），但期望值是外部人工锁定的——选择逻辑若有系统性 bug，产出值会撞常量而暴露。[实测] 用完全独立的第三方实现重算全部 golden 值并直连 live SEC 对账，三方吻合。

### 5.3 防线三：Validation 门禁（75 项）

按防御目标分组：**泛化门禁**（AST 扫描器保证业务代码零公司字面量；SIC 规则与注册表 profile 一致性）；**行为夹具**（第 11 家公司测试：Hilton/Citi/GM/ServiceNow 四家种子外真实公司的模拟数据流经真实抽取器，断言输出——Citi 夹具特意包含与实际比率**同维度**的监管阈值行，断言实际值被选中）；**语义门禁**（C03 禁用 fact 计数、恒等式检查、去 Ford 特例检查）；**召回棘轮**（OK 类状态格集合不得比上轮快照缩水，快照是只读夹具文件——防"修 A 坏 B"的静默能力退化）；**分层复审门**（stratified audit 对有值格分层抽样重审 quote 支撑性，任一 FAIL 直通 validation 红灯——且它是 correct-by-construction 的：门禁咬的是**现场重算**结果而非落盘文件，篡改 CSV 无效，[实测] 验证过）。

### 5.4 防线四：回归测试（17 个 unittest + 完整性重算）

验证体系自身也要能被证伪。轻量审核包（剔除大体积原始证据的包）曾有过"循环自证"缺陷：golden 校验只数 CSV 里的 PASS 字符串——包里自带一张写着全过的纸，然后验证纸上写着全过。终版的快照完整性校验做五类重算交叉：expected↔actual 逐行重比、G3/G4 对锁定夹具文件、golden 对 metrics_matrix 值漂移、G1 对 company_resolution、G2 对矩阵语义。[实测] 四向篡改全部拦截且诊断精确到行（`stored_status=PASS:recomputed=FAIL`、`fixture_expected_mismatch`、`metrics_value_drift:B01`）。模式判定为显式三态：证据齐全→FULL_VALIDATION（**优先于 marker**，误留 marker 无法降级完整工作区）；证据缺失+`LIGHT_REVIEW_PACKAGE.marker`→轻量模式；证据缺失无 marker→WORKSPACE_INCOMPLETE 硬失败（区分"审核者沙箱"与"工作区损坏"）。当前 17 个 unittest 还覆盖 Basel 阈值同维度对决、captive finance 召回/排除、FI value-level 夹具、iXBRL scale route、JPM CET1 金额 crosscheck、10-K/A full-instance 回退、AST 字符串拼接折叠和 I1-I8 实现映射。

---

## 6. 风险登记簿：已关闭项与仍开放项（截至 2026-07-09）

当前工作区 `python3 scripts/12_validate_repair.py` 返回全 P0 PASS，`python3 -m unittest tests/test_sec_pipeline_validation.py` 跑通 17 个测试。下面不再把旧审计项混作当前风险，而是分成**已关闭风险**与**仍开放风险**。

### 6.1 已关闭风险（代码已有实现 + validation/test 覆盖）

**C1 10-K/A full-instance 回退已实现。** 旧版只有 C04 的局部 AuditorName 回退；当前已有通用 `original_full_instance_fallback_row`：当 target 为 10-K/A、target instance 事实数少于 500、或缺关键 fact group 时，定位同报告期原始 10-K，并以 `source_role=target_original_full_instance` 写入 inventory。对应测试断言 amended target 能找到原始 10-K，sparse target 会触发 fallback reason。

**C2 Basel 裸 `wellcapitalized` 字缝已关闭。** `BASEL_THRESHOLD_CONCEPT_FRAGMENTS` 已包含裸 `wellcapitalized`，`BankingRegulation...RatioWellCapitalized` 这类无 minimum/required 修饰的阈值概念会被标成 regulatory threshold，不能成为 A01/A02 主值。同维度 actual-vs-threshold 对决测试确认实际比率胜出。

**C3 Captive finance 成员召回缺口已关闭。** 探针不再只做后缀锚定，而是对 debt fact 的 segment/legal-entity dimension member 做包含匹配，并带 `creditloss`、`creditfacility`、`financelease`、`supplierfinance` 等排除守卫。`GeneralMotorsFinancialCompanyIncMember` 和 `JohnDeereCapitalCorporationMember` 型成员已进入 fixture gate。

**C4 iXBRL scale route 已硬化。** `scaled_inline_value` 负责 scale/sign/括号负数归一化；`parse_instance_with_fallback()` 会先检测 `<ix:` 或 `xmlns:ix=`，inline 文件直接走 `InlineFactParser`，避免 XML streaming parser 把 `ix:nonFraction` 当普通 XML 节点而丢掉 `name/contextRef/unitRef/scale/sign`。当前验证包含 synthetic inline scale fixture 和 JPM CET1 capital = 294,804,000,000 的完整 evidence crosscheck。

**C5 FI 第 11 家行为夹具已升级到值级。** `mock_concept_inventory.csv` 已有 `expected_value` 列；`check_eleventh_company_behavior_financial_institution()` 断言 selected concept、context、dimensions、value 四项一致，能抓同概念错期间、错维度、错值。

**C6 AST 字符串拼接盲区已关闭。** 扫描器通过 `folded_ast_literal_value()` 折叠字符串 `BinOp(Add)`，`"Ford Motor " + "Company"` 不能再绕过公司身份字面量门禁。

### 6.2 仍开放风险（真实存在，扩展前应处理或接受）

**R1 FI 的 SIC 规则区间仍偏窄。** `profile_rules` 当前覆盖 6020–6029（国民商业银行），储蓄机构（6035/6036）、投行（6211）仍会默认进入非 FI profile，除非 registry override。修法是配置级扩区间，不需要改抽取器。

**R2 住宿表格机仍有单元格节奏召回风险。** 装配步假设“绝对值/变化值交替”节奏；三年度对比表（每 KPI 三个绝对值）等异构节奏会失配。但恒等式硬门会把它压成诚实空手，而不是错值。扩展到 Hilton/Hyatt 真实年报时，这仍可能是主要召回瓶颈。

**R3 召回棘轮仍需要下一轮真实变更检验。** 快照基线是只读夹具，形态正确；当前通过只能证明没有相对基线退化。它第一次真正咬合要等下一次指标产出发生真实变化。

**R4 B11 quote 的 raw_header 仍有可读性问题。** Marriott RevPAR 的证据 quote 已包含 parsed tokens、raw row 和恒等式误差，审计可复核；但 `raw_header` 截取窗口仍从句中开始，读起来不够干净。这是证据展示质量问题，不是数值或 gate 问题。

**R5 新金额类维度事实进入派生公式时必须新增金额级断言。** 当前 scale route 和 JPM CET1 capital crosscheck 已覆盖既有风险；但如果未来把其他维度金额用于公式，不能只依赖 parser 通用性，必须同步增加 metric-level golden 或 companyfacts/表格 crosscheck。

---

## 7. 如何扩展：从第 11 家到第 1000 家的操作手册

### 7.1 加一家公司（标准路径，预期零代码改动）

`config/company_registry.csv` 追加一行，十二列语义：

```text
company_id                机器标识（小写下划线）
display_name              显示名
primary_cik               SEC 主 CIK（在 submissions 页可查）
ticker                    股票代码
sic / sic_description     行业码及描述（submissions 返回，照抄）
industry_profile          行业档案（决定挂哪些抽取器）。可留待 SIC 规则
                          自动推导；与规则推导不一致时必须走 override 并留注记
                          （有一致性 validation 把关）
fiscal_year_end           财年末 MMDD（submissions 返回，照抄；管道所有期间
                          逻辑数据驱动于此，Macy's 的 0201 无任何特判代码）
target_period_policy      通常 latest_10k
entity_continuity_status  continuous；财年内换报告主体（并购继承）填 successor
                          类值——但即使填错，300–400 天 duration 前置条件和
                          CIK 链检查也会兜住 YoY 不可比判定（双保险，[实测]）
related_ciks / roles      Paramount 型双 CIK 场景：predecessor CIK 与角色标注，
                          事件扫描会自动跨 CIK
```

然后跑 M0→M7，读三样东西：`company_resolution.csv`（身份解析对不对）、`coverage_matrix.csv`（每个指标走了哪条通路、不可得的原因）、`exceptions_and_review_items.md`（全部待人工事项）。**期望心态**：新公司首跑出现 NOT_EXTRACTED/NEEDS_REVIEW 是正常且诚实的结果，出现"可疑的全绿"反而要警惕。

### 7.2 加一个行业

`metric_applicability.yaml` 三步：`profiles` 下新建 profile 并列出抽取器组合（标准五件套 + 行业特化件）；`profile_rules` 加 SIC 区间→profile 映射；`settings` 加该行业的词法配置（KPI 词表、量纲区间、口径优先序）。**判断新行业 KPI 用哪条通路的决策次序**：先查 us-gaap/行业分类账有没有标准概念（有→DIM_XBRL 通路，写概念解析器，零文本处理）；再查是否有公司普遍自定义扩展（→后缀/语义匹配）；最后才是 MD&A 文本表格（→复用 lodging 表格机骨架，换词表和不变量）。航空业示例：RASM/CASM/load factor 走文本通路，且存在恒等式 `RASM = PRASM口径修正 × load factor` 类关系可仿照 RevPAR 恒等式做列序自识别。

### 7.3 加一个抽取器（需要动代码的唯一场景）

模板即 lodging 表格机的五段结构：分段 → 锚定（配置化口径优先序）→ 装配 → **行业不变量硬门**（这是灵魂：找出该行业指标间的代数关系做既滤又排的双重角色）→ 量纲区间。同时**必须**配套：标记类注册进 EXTRACTOR_REGISTRY、第 11 家夹具加该行业一家真实公司的模拟数据 + 行为断言、validation 加对应门禁。没有夹具和门禁的抽取器等于没有防线的前线——守恒律会立刻找上它。

### 7.4 什么时候允许“公司适配”

为了避免从“过度公司特例化”摆到“过度泛化”，需要给公司适配一个合规通道。允许的公司适配必须满足六条：

```text
1. 适配对象是披露事实或实体关系，而不是为了凑数改公式。
2. 适配位置在 config / fixture / isolated adapter，不进入主控制流。
3. 有 SEC evidence 证明该公司披露形态确实不同。
4. 有 regression：至少一个 positive case 和一个 negative case。
5. exceptions 或 docs 写明为什么不能用行业规则解决。
6. 有复查条件：当第二家公司出现同类形态时，应提升为行业规则。
```

例子：Paramount 的 successor/predecessor CIK、Macy's 的实际 reportDate、Salesforce 的 fiscalYearEnd 都是合法配置级事实；`if company == "Salesforce" then parse sentence "as of January 31, 2026"` 是非法公司专属解析器；如果未来某家银行只有自定义 Basel 概念可用，可以先在配置中登记 concept alias，但必须同时把 alias 加入 Basel resolver 的 positive/negative fixture，而不是写公司分支。

### 7.5 Live 试点（毕业验收，强烈建议在批量扩展前执行）

静态防线只能防住“想得到的失败”；剩余风险按定义住在“想不到”里，只有真实世界能勘探。方案：Hilton（SIC 7011）、Citigroup（6021）、GM（3711）各填一行注册表，全管道真拉 SEC（成本约数百请求）。三个定向看点：Citi 的真实 Basel 标注检验 FI profile 规则是否需要扩到更宽 SIC 区间；Hilton 的真实表格排版检验恒等式列序自识别与 R2 节奏假设；GM 的真实 captive-finance member 检验 C3 的召回/排除守卫在野外是否足够。试点产出的 exceptions 清单，就是千家公司产品的第一份真实需求文档。

---

## 8. 文件地图与代码阅读路径

```text
scripts/
  sec_pipeline.py        全部逻辑单体（~14,000 行）。阅读入口见下。
  sec_http.py            UA/限速/退避/日志的 HTTP 客户端
  sec_urls.py            端点 URL 构造（CIK 补零等）
  00..12_*.py            十三个阶段薄封装，只调 run_stage
config/
  company_registry.csv   公司注册表（个体信息唯一合法居所）
  metric_applicability.yaml  行业 profile→抽取器 + SIC 规则 + 词法配置
tools/check_no_company_literals.py   AST 泛化门禁入口
tests/
  fixtures/sec_10_company_spike/golden_expected_values.csv   锁定期望值
  fixtures/eleventh_company_smoke/   第 11 家行为夹具（4 行业真实公司模拟数据）
  fixtures/regression/previous_ok_status_snapshot.csv        召回棘轮基线
  test_sec_pipeline_validation.py    17 个 unittest 回归测试
outputs/   （每个 CSV 的 schema 在 03 号指令文档第 6 节）
  metrics_matrix.csv     主交付物：230 行、20 列；整行才是最小可审计单元
  metric_evidence.csv    证据明细（quote/原文/解析方法）
  coverage_matrix.csv    每格的通路与可得性归因
  golden_results.csv     63 条断言结果
  repair_validation_results.csv   75 项门禁结果
  basel_ratio_candidates.csv      比率候选全集（含 role 标注的阈值上下文）
  stratified_audit.csv / scalability_audit.csv / events.csv
  governance_signals.csv / risk_legal_signals.csv
  company_resolution.csv / latest_filings_inventory.csv
  exceptions_and_review_items.md  全部待人工事项
evidence/（完整包才有）  requests_log.csv + 全部原始 SEC 响应落盘
LIGHT_REVIEW_PACKAGE.marker   轻量审核包的显式声明标记
```

**代码阅读路径**（按依赖序，约半天可通读骨架）：`run_stage` 调度表（尾部）→ `validation_package_mode` 三态判定 → `select_component` 选择算法（全项目的取数心脏）→ `load_company_registry` + `extractor_names_for_profile` 派发链 → 一个完整抽取器（推荐 lodging 五段式）→ `stage_run_golden_assertions` + `light_golden_snapshot_integrity_failures` 验证双通路 → `check_*` 系列门禁。

---



## 9. 输出文件怎么读：从矩阵到证据的导航方法

这一节是实操入口。前面的章节解释了系统为什么这么设计；这里解释拿到一个交付包以后，应该按什么顺序打开文件、看什么字段、如何判断一个数字是否可信。

### 9.1 `metrics_matrix.csv`：主交付物，不是唯一证据

`metrics_matrix.csv` 是所有指标的主矩阵。每一行代表一个 `company × metric_id`，但它不是单纯的 value，而是一个带状态、来源、期间和证据锚点的指标判断。

一行回答的是这个问题：

```text
在某家公司、某个目标报告期内，某个指标是否有可消费结果？
如果有，值是什么、单位是什么、从哪份 SEC 申报来的、用什么概念/章节取到；
如果没有，缺口的语义是什么、下一步应该怎么处理。
```

正确读法是按这个顺序：

```text
1 看 status：这一行能不能直接消费。
2 看 source_class：它来自标准 XBRL、维度 XBRL、MD&A、DEF14A、8-K 还是文本。
3 看 value/unit：有数值时才解释量纲；空值不自动等于失败。
4 看 concept_or_section/context_or_dimension：确认取数口径是不是要的口径。
5 看 accession/filed_date/period_start/period_end：确认是哪份申报、哪个期间。
6 看 notes/confidence：确认是否有 proxy、替代值、边界或人工复核要求。
```

最先看这些字段：

```text
company / cik                  公司身份
metric_id / metric_name         指标编号与名称
value / unit                    数值与单位；无数值时 value 可为空
status                          语义状态，是下游判断的合同语言
source_class                    STD_XBRL / DIM_XBRL / DERIVED / MDA / DEF14A / 8K_ITEM / TEXT 等
formula                         派生公式或选择规则摘要
period_start / period_end        期间，判断是否目标财年
accession / form / filed_date    来源申报
concept_or_section               XBRL concept 或文本章节
context_or_dimension             XBRL context / dimension 口径
confidence / notes               置信度和关键 caveat
```

使用矩阵时要遵守一个习惯：**只在矩阵里看到 value 不够，必须去 `metric_evidence.csv` 追证据。** 第一轮最大事故正是矩阵里有 value、有 status、有 quote，但 quote 根本不支撑 value。

### 9.2 `metric_evidence.csv`：数值的证据链

每个 OK 类数值都应该能在这里找到对应证据。人工审计时按 `company + metric_id` join：

```text
company,cik,metric_id
source_url,local_path,accession,document_name
concept_or_section,context_or_dimension,unit
period_start,period_end
value_raw,value_normalized
evidence_quote,extraction_method,parser_version
```

判断证据是否合格，不是看列是否填了，而是看三件事：

1. **对象一致**：quote / concept 是否真的说的是这个指标。RevPAR 的 quote 必须有 RevPAR 或 revenue per available room，C03 必须是 PeoTotalCompAmt 或薪酬表，不是 ecd fact 数量。
2. **期间一致**：period_end 是否等于目标财年末，期间型是否是 300–400 天，而不是季度或 stub period。
3. **口径一致**：JPM A01/A02 必须说明 Basel standardized / advanced、parent / bank subsidiary；Salesforce B12 必须说 RPO/cRPO 不是 ARR。

### 9.3 `coverage_matrix.csv`：每个格子的可得性解释

它回答的问题不是“有没有数值”，而是“这个指标为什么是这个状态”。特别看：

```text
has_numeric_value
has_evidence
needs_text_extraction
needs_review
reason
```

专家级审计要警惕两类污染：

```text
has_evidence 全部置 1，但 evidence 表实际缺行。
NOT_AVAILABLE_SEC 被滥用来掩盖“代码没消费已有 inventory”。
```

### 9.4 `golden_results.csv`：锁定值断言

Golden 是防止“代码跑通但数字错”的核心。关键字段：

```text
assertion_id,description,expected,actual,status,evidence_path,notes
```

完整包模式下，golden 应该从原始 evidence / companyfacts 重算；轻量包模式下，至少要做 snapshot integrity：expected/actual/status 重新比较、对 fixture、对 metrics_matrix、对 company_resolution。只数 `status=PASS` 是循环自证，已经被修掉。

### 9.5 `repair_validation_results.csv`：门禁结果，不等于业务结果

这个文件记录的是验证门禁，包括去公司特例化、Basel threshold、light golden integrity、stratified audit、11 家行为测试等。读它时要看三种状态：

```text
PASS                       检查执行且通过
SKIPPED_LIGHT_PACKAGE       轻量包缺重型 evidence，检查被诚实跳过
PASS_LIGHT_REVIEW           轻量包自洽通过，但不是完整 evidence 验收
```

不要把 `PASS_LIGHT_REVIEW` 当成完整项目 ACCEPT。轻量包只能说明代码/快照/配置自洽，不能说明所有 SEC 原始证据齐全。

### 9.6 `basel_ratio_candidates.csv`：Actual ratio 与 threshold 的分离层

这是 round3 hardening 后的重要输出。银行资本比率表里会同时披露：

```text
actual_ratio              公司实际资本比率，例如 CET1 = 14.6%
regulatory_threshold      监管最低要求、well-capitalized 要求，例如 7.0%
```

A01/A02 的主值只能来自 `actual_ratio`。threshold 可以保留用于上下文，但不能进入 `metric_evidence.csv` 支撑主值。专家审计银行指标时必须打开这个文件看候选角色分离是否正确。

---

## 10. 如何人工审计一个指标：从 value 追到 SEC 事实

下面是一套可重复的人工审计流程。任何一个有数值的格子，都可以按这 7 步查。

### 10.1 七步审计法

```text
1. 在 metrics_matrix.csv 找 company + metric_id。
2. 检查 status/source_class/value/unit/period/accession。
3. 在 metric_evidence.csv join 同一个 company + metric_id。
4. 打开 local_path 或 evidence_quote，确认 quote/concept 支撑 value。
5. 检查 formula 是否符合 02 指标定义。
6. 检查 status 是否诚实：抽不到就 NOT_EXTRACTED，不适用就 N_A_STRUCTURAL，不可比就 NOT_MEANINGFUL。
7. 若该值属于 golden / validation 保护范围，查看 golden_results 或 repair_validation 是否覆盖它。
```

### 10.2 示例：Marriott B11 RevPAR

专家应该能回答：

```text
value = 128.8 USD
status = MDA_OK
source_class = MDA
证据是否有 raw_header / raw_row / parsed？
raw_header 是否包含 RevPAR / Occupancy / ADR？
RevPAR ≈ ADR × Occupancy / 100 是否成立？
是否误把 RevPAR increased 2.0% 当成 2.0 USD？
```

只要 evidence_quote 没有原文表头或选中行，即使 value 看起来合理，也不能算完整证据。

### 10.3 示例：Salesforce B12 RPO/cRPO

专家应该能回答：

```text
value = 72.4B USD
status = DIM_XBRL_OK
concept = RevenueRemainingPerformanceObligation
RPO != ARR，cRPO != ARR 是否写入 notes？
是否优先消费 accession instance，而不是文本正则？
current + noncurrent 是否可加总回 total RPO？
```

Salesforce 的历史事故说明：如果 instance 里已经有结构化 concept，再用公司专属文本正则，是错误方向。

### 10.4 示例：JPM A02 CET1 ratio

专家应该能回答：

```text
主值是不是 actual ratio，而不是 regulatory threshold？
unit 是否 pure？
dimensions 是否含 RiskWeightedAssetsCalculationMethodologyAxis？
口径是否说明 standardized / advanced、parent / bank subsidiary？
metric_evidence 是否排除了 Minimum / Required / WellCapitalized 这类阈值概念？
```

这类指标的陷阱是：actual ratio 与 regulatory threshold 长得几乎一模一样，都是 pure、同期间、同 Basel 维度。只能靠 concept role 和词法排除来防错。

### 10.5 示例：C03 CEO compensation

专家应该能回答：

```text
concept 是否是 PeoTotalCompAmt？
unit 是否 USD？
period 是否目标财年？
多 PEO 情况是否没有乱求和？
是否还残留 ecd_fact_count 这种伪指标？
```

C03 是本项目的正例：遍历所有公司、统一按标准 ecd concept 过滤，是天然可扩展的属性范式。

---

## 11. 常见错误模式与定位方式

### 11.1 有 value，但 evidence 不支持

症状：矩阵中 status 是 `MDA_OK` 或 `DEF14A_OK`，但 quote 是目录、iXBRL context 噪声、无关段落或关键词附近的随机句子。

定位：

```bash
# 手工 join company + metric_id
# 看 evidence_quote 是否包含指标关键词和原始数值
```

处理：降级为 `NOT_EXTRACTED` 或修 extractor，不能保留 OK。

### 11.2 concept 命中了 threshold，不是 actual value

症状：银行资本比率值等于监管最低要求，例如 7.0%、6.5%，而不是公司实际比率。

定位：打开 `basel_ratio_candidates.csv`，看 `candidate_role`。

处理：threshold 保留为上下文，不进入 `metric_evidence.csv` 主证据。

### 11.3 文本 KPI 把 percentage change 当 absolute value

症状：RevPAR = 2.0 USD、occupancy = 1.5% 这类明显不合理结果。

定位：quote 中出现 increased / decreased / percentage / bps，但没有绝对值表格。

处理：加量纲区间 + quote 关键词 + 行业恒等式，例如 RevPAR = ADR × occupancy。

### 11.4 公司名特例回潮

症状：生产代码里出现：

```python
if company == "Salesforce":
if cik == 1108524:
pattern = "January 31, 2026"
```

处理：公司名只能在 config / fixtures / docs；业务逻辑必须由 profile、SIC、concept、dimension、text probe 触发。

### 11.5 轻量包伪装完整验证

症状：缺 evidence / concept_inventory，却报告 full PASS。

处理：必须有 `LIGHT_REVIEW_PACKAGE.marker`；轻量模式输出 `PASS_LIGHT_REVIEW` 或 `PASS_LIGHT_GOLDEN_INTEGRITY`，不能冒充 full validation。

### 11.6 coverage 与 evidence 不一致

症状：coverage 写 `has_evidence=1`，但 metric_evidence 没对应行。

处理：coverage 必须由 metrics_matrix 与 metric_evidence 实际 join 生成，而不是全量置 1。

---

## 12. 验收模式：轻量审核包 vs 完整 evidence 包

### 12.1 轻量审核包可以验什么

轻量包适合验：

```text
代码结构是否去公司特例化；
config/profile/extractor registry 是否存在；
validation snapshot 是否自洽；
golden snapshot integrity 是否能防篡改；
scalability_audit 是否 0 violation；
第 11 家行为夹具是否能跑；
stratified audit 是否全 PASS。
```

轻量包不适合验：

```text
SEC 原始响应是否真实存在；
requests_log 是否覆盖所有请求；
companyfacts / submissions / accession materials 是否完整；
完整 concept_inventory 是否可重算；
所有 evidence local_path 是否能打开。
```

### 12.2 完整包正式验收顺序

拿到完整包后，按这个顺序做：

```bash
python3 scripts/00_smoke_test_sec_access.py
python3 scripts/01_resolve_companies.py
python3 scripts/02_inventory_filings.py
python3 scripts/03_companyfacts_inventory.py
python3 scripts/04_compute_standard_metrics.py
python3 scripts/05_fetch_accession_materials.py
python3 scripts/06_parse_xbrl_instances.py
python3 scripts/07_extract_8k_events.py
python3 scripts/08_extract_def14a.py
python3 scripts/09_extract_mda_and_risk_text.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/11_build_report.py
python3 scripts/12_validate_repair.py
python3 tools/check_no_company_literals.py
```

然后检查：

```text
evidence/requests_log.csv 是否 SEC-only；
evidence/submissions/、companyfacts/、accession_materials/ 是否齐全；
golden_results.csv 是否全 PASS；
repair_validation_results.csv 是否无 FAIL；
stratified_audit.csv 是否全 PASS；
REPORT verdict 是否与门禁一致；
exceptions 是否列出剩余 NOT_EXTRACTED / NEEDS_REVIEW。
```

### 12.3 分层抽查策略

不要随机抽 20 个值，因为 STD_XBRL 干净指标太多，会稀释问题。建议分层抽：

| 来源层 | 抽查数量 | 关注点 |
|---|---:|---|
| STD_XBRL / DERIVED | 8 | concept、period、formula、candidate chain |
| DIM_XBRL | 4 | dimensions、actual vs threshold、unit=pure/USD |
| MDA / TEXT | 3 | quote 原文性、表头、段落定位 |
| DEF14A | 3 | ecd concept、薪酬口径、多 PEO |
| 8K_ITEM | 2 | hdr.sgml `<ITEMS>`、item mapping |

### 12.4 Verdict 规则

```text
ACCEPT：完整包、证据链、golden、coverage、报告、无第三方补数全部通过。
ACCEPT WITH CAVEATS：少量文本/MD&A/DEF14A 抽取失败，但诚实标 NOT_EXTRACTED，并有 exceptions。
REJECT：缺核心文件、无证据数值、第三方补数、golden fail 仍报成功、关键口径错用、无法复现。
```

---

## 13. 生产化路线图：从 spike 到可运营系统

### 13.1 近期：真实第 11 家试点

在批量扩展前，不要继续只打磨静态 validation。应该新增 3–4 家真实公司，跑 live SEC：

```text
Hilton / Hyatt：检验 lodging 表格机。
Citigroup / Bank of America：检验 Basel concept resolver、threshold 排除、FI profile。
GM / John Deere / Caterpillar：检验 captive finance debt 口径。
ServiceNow / Adobe：检验 RPO/cRPO instance-first。
```

试点不是为了拿漂亮结果，而是为了暴露真实 filing 的排版、namespace、dimension、period edge case。

### 13.2 中期：模块化拆分

当前 `sec_pipeline.py` 是 spike 单体。产品化建议拆成：

```text
sec_client/              HTTP、限速、retry、requests_log
filing_inventory/        submissions、target/prior/DEF14A/8-K 定位
xbrl_parser/             companyfacts + accession instance parser
extractors/              Standard, Basel, RPO, Lodging, DEF14A, AuditorName, 8K, RiskText
validators/              golden, repair, scalability, stratified audit, tamper regression
reporting/               matrix、coverage、exceptions、report
config/                  company registry、metric applicability、concept maps
```

拆分时不要先追求“漂亮类结构”，要先保留现有门禁。没有 validation 的重构只是代码搬家。

### 13.3 中期：存储层升级

CSV 足够 spike，但千家公司会遇到 join、版本、审计查询的问题。建议升级到：

```text
raw evidence object store       原始 SEC 响应
SQLite/DuckDB/Postgres          facts、metrics、evidence、coverage
versioned run_id                每次运行可复现
immutable expected fixtures      golden / recall baseline 只读
```

核心数据模型：

```text
company
filing
fact
metric_result
metric_evidence
validation_result
exception_item
```

### 13.4 长期：CI/CD 与回归套件

每个 PR 必须跑：

```text
unit tests：concept resolver、period selector、text parser
fixture tests：第 11 家公司行为测试
golden tests：Enphase/Ford 等基准
scalability gate：公司字面量扫描
light integrity：snapshot tamper regression
full integration：定期 live SEC 小样本
```

### 13.5 长期：人工复核界面

`NEEDS_REVIEW` 不应永远停在 CSV。产品化后应有复核工作台：

```text
显示矩阵值 + evidence quote + 原文链接；
允许 reviewer 选择 approve / reject / override status；
所有人工决定写 audit trail；
下一轮 extractor 从人工复核中学习失败模式，但不得直接硬编码公司名。
```

---

## 14. 训练清单

读完本文档后，应该能做这些事：

1. **手工追一个值**：从 `metrics_matrix.csv` 找到 value，再到 `metric_evidence.csv`，再到 raw evidence 或 quote。
2. **判断 status 是否诚实**：知道 `NOT_AVAILABLE_SEC`、`NOT_EXTRACTED`、`NOT_MEANINGFUL`、`N_A_STRUCTURAL` 的边界。
3. **识别 actual value 与 context/threshold/noise**：尤其是银行资本比率、RevPAR、RPO、C03 薪酬。
4. **区分行业特化和公司特例**：SIC/profile/extractor 是合法行业抽象；`if company == ...` 是危险信号。
5. **新增公司不改代码**：只改 registry，跑 validation，读 exceptions。
6. **设计一个新 extractor**：先定义口径、数据源、证据、状态，再写抽取逻辑，最后写 validation 和 fixture。
7. **给 Codex 下正确指令**：不要说“修 Salesforce”，要说“RpoCrpoExtractor 优先消费 instance fact；禁止公司名分支；新增行为夹具”。

最终形成一个简单判断：

```text
一个数字可信 = 来源可信 + 口径正确 + 期间正确 + 证据支撑 + 门禁覆盖。
少任何一项，都只是“看起来像数字”。
```

---

## 15. 快速命令手册

### 15.1 轻量包审核

```bash
python3 -m py_compile scripts/sec_pipeline.py tools/check_no_company_literals.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/12_validate_repair.py
python3 tools/check_no_company_literals.py
```

预期：

```text
PASS_LIGHT_GOLDEN_INTEGRITY
PASS_LIGHT_REVIEW
scalability_audit.csv = 0 violations
```

### 15.2 完整包复跑

```bash
python3 scripts/00_smoke_test_sec_access.py
python3 scripts/01_resolve_companies.py
python3 scripts/02_inventory_filings.py
python3 scripts/03_companyfacts_inventory.py
python3 scripts/04_compute_standard_metrics.py
python3 scripts/05_fetch_accession_materials.py
python3 scripts/06_parse_xbrl_instances.py
python3 scripts/07_extract_8k_events.py
python3 scripts/08_extract_def14a.py
python3 scripts/09_extract_mda_and_risk_text.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/11_build_report.py
python3 scripts/12_validate_repair.py
```

### 15.3 常用 grep / 审计命令

```bash
# 查公司名特例回潮
grep -RIn "JPMorgan Chase\|Marriott International\|Salesforce\|Ford Motor Company\|Paramount\|Enphase" scripts/ tools/

# 查第三方数据源
grep -RIn "yfinance\|bloomberg\|refinitiv\|macrotrends\|stockanalysis\|wikipedia" scripts/ .

# 查可能绕过 golden 的硬编码
grep -RIn "expected_value\|golden\|hardcode" scripts/ tests/

# 快速看失败门禁
python3 - <<'PYCODE'
import csv
for r in csv.DictReader(open('outputs/repair_validation_results.csv')):
    if r.get('status') not in {'PASS','SKIPPED_LIGHT_PACKAGE','PASS_LIGHT_REVIEW','PASS_LIGHT_GOLDEN_INTEGRITY'}:
        print(r)
PYCODE
```



## 16. 术语表

```text
spike              为验证可行性的一次性探索开发
accession          SEC 申报唯一编号（如 0001463101-26-000013）
10-K / 10-K/A      年报 / 年报修正案
8-K / DEF 14A      重大事项即时报告 / 股东大会委托书
XBRL / iXBRL       财务事实标签化标准 / 其嵌入 HTML 的内联形态
concept            事实的语义标签名；us-gaap=标准分类账，公司域名=自定义扩展
dimension          轴(axis)+成员(member)构成的事实限定
unit: pure / USD   纯数（比率）/ 美元金额
scale              iXBRL 数字的 10 幂缩放声明；helper 与 parse route 已有
                   回归覆盖；新增金额类消费仍需金额级断言，见 R5
companyfacts       SEC 的公司级标准事实聚合 API（无维度事实）
hdr.sgml           申报头文件，含 8-K 的 <ITEMS> 事项列表
ecd                委托书高管薪酬 XBRL 分类账（pay-versus-performance 规则）
SIC                SEC 四位行业分类码
ASC 606/842/326    收入确认 / 租赁 / 信用损失会计准则（分别解释 RPO 普适、
                   FinanceLease 概念普遍存在、CreditLoss 概念普遍存在）
CET1 / Tier 1      普通股一级资本 / 一级资本（银行监管资本层级）
RWA                风险加权资产；资本比率的分母
Basel 标准法/高级法  两种 RWA 计算方法学（standardized / advanced）
监管阈值            资本充足及格线(7.0%)、well-capitalized 线(6.5%)等最低要求，
                   与实际比率同格式共存于年报，须词法隔离
RPO / cRPO         合同剩余履约义务 / 其未来 12 个月内部分（≠ARR）
RevPAR/ADR/occupancy  每间可售房收入/平均房价/入住率；RevPAR=ADR×occupancy
captive finance    企业专属金融子公司（Ford Credit 型）
stub period        存续残段：主体年中成立导致的不足一年报告期
候选链              同一指标按优先级排列的概念探测序列
golden 断言        对基准公司的人工锁定期望值，管道必须独立复现
守恒律              本项目对 Goodhart 定律的工程表述：门禁边界即质量边界，
                   缺陷向未度量维度迁移
correct-by-construction  构造即正确：门禁咬现场重算而非落盘文件，篡改无效
tamper test        篡改测试：故意破坏输入验证防线是否真有牙
LIGHT_REVIEW_MODE  剔除大体积证据的审核包模式，须显式 marker 声明
```

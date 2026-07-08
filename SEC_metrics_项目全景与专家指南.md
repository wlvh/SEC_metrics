# 05｜项目全景与专家指南：SEC 十公司财务指标计算系统

定位：让读者完全掌握本项目——它是什么、架构如何、数字怎么算出来、准确性靠什么保证、如何扩展到第 11 家乃至第 1000 家公司。

---

## 0. 这份文档的可信度声明（先读这一节）

本文档是由审计方基于直接代码考证写成。开发方文档描述的是意图（代码想做什么），本文档描述的是经过验证的现实。

每条关键论断带三级可信度标记：

```text
[实测]   我执行过代码或对抗测试，有运行结果为证
[考证]   我读过实现原文，逐行确认过逻辑
[声明]   来自 Codex/文档的声明，我未独立验证
```

全文未标注处默认为 [考证] 级。凡 [声明] 级都会显式标出。


---

## 1. 项目是什么：一句话、边界与交付物实况

**一句话**：直接连接 SEC（美国证券交易委员会）官方数据端点，对 10 家不同行业的美国上市公司，计算最近一个已申报财年的财务、治理、风险与事件指标，输出每个数值都可追溯到 SEC 原始响应的指标矩阵。

**任务性质**是一次 spike——工程术语，指为验证可行性而做的一次性探索开发，不是生产系统。它的成功标准写在 01 号 SOP 里且值得背下来：**不是"所有指标都有数值"，而是每家公司 × 每个指标都有 value / status / formula / source / evidence / confidence 六件套**。找不到数据时诚实标状态是合法结果；为填满矩阵而猜数是失败。这条价值观贯穿了后面所有的机制设计。

终版交付物实况：

```text
指标矩阵      230 行 = 10 家公司 × 22~27 个指标
有数值的格    151 个，全部带证据链
状态分布      OK 69 | TEXT_QUAL 54 | NOT_AVAILABLE_SEC 42 | 8K_ITEM_OK 30
              DIM_XBRL_OK 12 | DEF14A_OK 8 | NOT_EXTRACTED 7
              NOT_MEANINGFUL 3 | MDA_OK 2 | NEEDS_REVIEW 2 | N_A_STRUCTURAL 1
来源分布      8K事件 60 | 派生计算 44 | 标准XBRL 25 | 维度XBRL 12 | 委托书 8 | MD&A 2
验证体系      57 条 golden 断言 + 38 项 repair validation + 7 个篡改回归单元测试
              + 泛化扫描器 + 分层抽样复审 + 第 11 家公司行为夹具
代码规模      sec_pipeline.py 单体约 10,500 行 + 13 个编号阶段脚本（各约 20 行薄封装）
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

XBRL（eXtensible Business Reporting Language）是把财务数字变成机器可读标签的标准。iXBRL（inline XBRL）是它的现代形态：标签直接嵌在人类阅读的 HTML 年报正文里，同一份文件人机两用。五个必懂概念：

- **concept（概念/标签）**：一个数字的语义名字，如 `RevenueFromContractWithCustomerExcludingAssessedTax`。分两类：**标准概念**属于 us-gaap 分类账（namespace 是 `fasb.org/us-gaap/...`，全市场通用）；**公司扩展**是公司自造的标签（namespace 是公司域名，如 JPM 自造的 `CommonEquityTier1CapitaltoRiskWeightedAssets`——注意那个不合规范的小写 to，就是自造的胎记）。**同一个经济事实，不同公司可能用不同标签**，这是候选链机制存在的根本原因。
- **context（上下文）**：数字属于哪个期间、哪个报告主体、带什么维度。
- **dimension（维度）= axis（轴）+ member（成员）**：给事实加限定。例如 `us-gaap:RiskWeightedAssetsCalculationMethodologyAxis = jpm:BaselIIIStandardizedMember` 表示"这个资本比率是按 Basel III 标准法算的"。轴通常是标准的，成员经常是公司自造的——这个不对称是泛化设计的关键约束。
- **unit（单位）**：`iso4217:USD` 是美元金额，`pure` 是纯数（比率）。
- **scale（缩放属性）**：iXBRL 数字标签可声明 10 的幂缩放（正文显示 294,804 百万，标签值 294804 + scale=6）。v1.0 曾把本项目误判为“未处理 scale”，0708 复核后撤销：代码中已有 `scaled_inline_value`，当前各轮 JPM CET1 资本金额产物也为正确量级。正确的残余风险不是“scale 未实现”，而是**缺专项回归测试和金额类消费验证**：比率类 `pure` 事实当前安全；金额类维度事实若未来进入派生公式，必须先通过 scale regression 与 companyfacts/表格交叉核验。详见 R4。

### 2.3 HTTP 访问纪律

[考证+实测] `sec_http.py` 实现：所有请求带 `User-Agent: <组织> <邮箱>`（SEC 硬性要求，缺失会 403）；全局限速 ≤5 请求/秒（sleep 节流）；403/429/5xx 指数退避重试（第一轮的请求日志里能看到 403→重试→200 的完整链）；每次请求写入 `evidence/requests_log.csv`；原始响应落盘。第一轮审计对 592 条请求做过域名普查：**只有 www.sec.gov 和 data.sec.gov 两个域名**，零第三方数据源——"不得用模型记忆或第三方补数"这条硬约束是被验证过的，不只是写在纸上。

---

## 3. 架构总览：单体、流水线与知识安置三原则

### 3.1 物理形态：一个单体 + 十三个薄封装

全部逻辑住在 `scripts/sec_pipeline.py`（约 10,500 行）这一个单体模块里；`00_smoke_test_sec_access.py` 到 `12_validate_repair.py` 十三个编号脚本各约 20 行，只做一件事：`run_stage(stage_name="...")`。调度表在单体尾部的 `STAGES` 字典。这个形态是 spike 阶段的务实选择，产品化时应拆分——但拆分时**必须保留的**是下面的逻辑架构，那才是五轮迭代真正沉淀的资产。

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

每阶段的输出既是下一阶段的输入，也是独立可审计的中间产物——这个"每层落盘"的设计让第三方（比如我）能在任意断面重算验证。

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

具体落地：`config/company_registry.csv` 承载全部个体信息（逐列语义见第 7 节）；`config/metric_applicability.yaml` 以**行业 profile** 为键定义每个 profile 挂载哪些抽取器（`lodging → LodgingKpiExtractor`，`financial_institution → BaselCapitalRatioExtractor`……），并含 `profile_rules`（SIC 区间到 profile 的自动推导规则）与 `settings`（量纲区间、scope 优先序等词法配置）；业务代码通过 `has_extractor(extractors, "XxxExtractor")` 这样的**能力查询**派发，抽取器类本身是空的标记类（capability tag）。[实测] 当前生产路径中没有发现公司身份业务分支；内置 AST 扫描器已覆盖常量、调用参数、字典键等常见逃逸形态。但它仍未做字符串拼接常量折叠，理论上可被 `"Ford Motor " + "Company"` 绕过，见 R8。


---

### 3.4 通用性不是目标：正确性与工程量的适配治理

本项目把“公司特例”赶出生产控制流，这是必要的，但容易让人误解成“越通用越好”。这不是正确目标。两个目标：**足够正确**和**工程量可控**。通用性只是同时服务这两个目标的手段；当通用性开始牺牲正确性，或者为了覆盖所有可能命名而写出更复杂、更脆弱的解析器，它就从资产变成负债。

更好的判断框架是四层适配纪律：

```text
第 0 层：不可妥协的通用骨架
  SEC-only、证据链、period 选择、status 语义、golden/validation、请求日志。
  这些必须全公司一致。

第 1 层：指标级通用逻辑
  companyfacts 选择算法、RPO 标准概念、AuditorName、ecd:PeoTotalCompAmt。
  只要 SEC/XBRL 标准已经给了结构化事实，就优先使用，不写文本正则。

第 2 层：行业/业务模式级适配
  金融机构 Basel、住宿业 RevPAR、SaaS/合同履约 RPO、制造业 captive finance。
  这些适配是合理的，因为同一行业共享披露习惯、单位和不变量。

第 3 层：配置级公司事实
  CIK、fiscalYearEnd、successor/predecessor、related_ciks、roles、人工 override。
  这些可以按公司写入 registry，因为它们是输入事实，不是计算逻辑。

第 4 层：受控公司补丁（默认禁止，但不是永远禁止）
  只有在高价值公司、公开披露形态确实独特、行业抽象代价过高时才允许。
  条件是：必须隔离成 data/config 或 adapter；必须有 evidence；必须有 regression；
  必须在 exceptions 中解释；必须有迁移/过期条件；不得污染主路径。
```

Basel 资本比率解析器给了一个反面教材：从 JPM 私有概念出发追求“泛化”，一度写出过宽的概念匹配器，导致监管最低要求可能赢过实际资本比率。正确做法不是回到 `if company == "JPM"`，也不是写一个无限宽的语义正则，而是**正负词表 + 标准轴锚定 + 候选角色分离 + 行为级 fixture**。换句话说，好的泛化不是“我能匹配更多字符串”，而是“我知道哪些字符串绝不能成为主值”。

因此，扩展到上千家公司时不要追求一次性全覆盖。建议按行业簇推进：每一簇先选 3–5 家真实公司做 live pilot，抽取器以**高精度优先**；抽不到时宁可 `NOT_EXTRACTED` / `NEEDS_REVIEW`，不要让泛化器产生伪 OK 数值。等同一失败模式重复出现，再把它提升为行业规则或标准 extractor。
---

## 4. 数字是怎么算出来的：五条数据通路逐一拆解

矩阵里 151 个有值格来自五条通路，每条的机制、防错设计和已知边界如下。

### 4.1 通路一：STD_XBRL 标准指标 + DERIVED 派生（69 格，营收/净利/资产/现金流等）

**选择算法**（02 号定义文档锁定，[实测] 我用完全独立的实现重算过 Enphase/Ford 全部数值并与 live SEC 对账吻合）：

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
             tobewellcapitalized / capitaladequacyminimum 等即拒绝；
             当前仍保留裸 wellcapitalized 字缝，见 R2）
         AND 语义匹配：
             规范化 = 小写去符号，且 tierone 统一替换为 tier1
             含 riskweightedassets 或 riskbasedcapitalratio 之一
             A02 要求含 commonequitytier1 或 cet1
             A01 要求含 tier1 且非 CET1（防 CET1 被错归 Tier 1）
选择排序 = ParentCompanyMember/合并口径优先 > Standardized 优先
         > 无 LegalEntityAxis 优先 > context 字典序
```

三条设计原理值得记住：**(a)** 锚定在标准轴而非成员——各银行的成员名各不相同（`jpm:BaselIIIStandardizedMember` vs 其他行的自造名）但轴是 us-gaap 标准的；**(b)** tierone→tier1 统一——us-gaap 官方命名用拼写式 TierOne，JPM 扩展用数字式 Tier1，不统一就会漏配标准命名（这是第三轮修掉的真 bug，[实测] 拼写式 CET1 曾被错分类为 A01）；**(c)** 阈值排除——银行 10-K 同时标注实际比率和**监管最低要求**（及格线 7.0%、well-capitalized 线 6.5%），两者单位维度期间全同，不做词法排除的话监管及格线可能被选为银行的实际比率（[实测] 第四轮曾用同维度对决打穿过，round3 已在候选池阶段剔除主要阈值族）。被排除的阈值事实**不丢弃**，移入 `basel_ratio_candidates.csv` 带 `candidate_role=regulatory_threshold` 标注——它们是有价值的上下文（实际比率距及格线的距离就是资本缓冲）。终版 JPM 输出：A01=0.155、A02=0.146（母公司合并口径，Basel 口径在 notes 注明）。

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

### 5.2 防线二：Golden 断言体系（57 条）

Golden 断言是"代码跑通但数字错"的专用解毒剂：对两家基准公司（Enphase=干净标准 XBRL、Ford=专门踩坑）的全部核心数值，由人工事先从原始年报核出**锁定期望值**（存于 `tests/fixtures/sec_10_company_spike/golden_expected_values.csv`），管道必须独立复现出完全相同的数字。分四组：G1 结构断言（10 家 CIK/财年末）、G2 防误用断言（故意确认 JPM 无流动资产端点、Ford 无常规 capex 概念——**把"预期中的缺失"也固化为断言**，防止未来有人"好心修复"）、G3/G4 数值断言（Enphase 13 值 + Ford 11 值，含派生量和命中标签断言）、G5 候选值（其余 8 家 × 3 值供人工核对）。铁律：**断言失败即停机报告实际值，不得修改期望值，不得硬编码绕过**。独立性论证：断言与计算共享选择函数（同一单体），但期望值是外部人工锁定的——选择逻辑若有系统性 bug，产出值会撞常量而暴露。[实测] 我用完全独立的第三方实现重算全部 golden 值并直连 live SEC 对账，三方吻合。

### 5.3 防线三：Validation 门禁（38 项）

按防御目标分组：**泛化门禁**（AST 扫描器保证业务代码零公司字面量；SIC 规则与注册表 profile 一致性）；**行为夹具**（第 11 家公司测试：Hilton/Citi/GM/ServiceNow 四家种子外真实公司的模拟数据流经真实抽取器，断言输出。Citi 夹具已用于验证 Basel 选择路径，但当前 FI 夹具仍主要是 concept-level，尚未断言 selected value，见 R6）；**语义门禁**（C03 禁用 fact 计数、恒等式检查、去 Ford 特例检查）；**召回棘轮**（OK 类状态格集合不得比上轮快照缩水，快照是只读夹具文件——防"修 A 坏 B"的静默能力退化）；**分层复审门**（stratified audit 对有值格分层抽样重审 quote 支撑性，任一 FAIL 直通 validation 红灯——且它是 correct-by-construction 的：门禁咬的是**现场重算**结果而非落盘文件，篡改 CSV 无效，[实测] 验证过）。

### 5.4 防线四：篡改回归（7 个单元测试 + 完整性重算）

验证体系自身也要能被证伪。轻量审核包（剔除大体积原始证据的包）曾有过"循环自证"缺陷：golden 校验只数 CSV 里的 PASS 字符串——包里自带一张写着全过的纸，然后验证纸上写着全过。终版的快照完整性校验做五类重算交叉：expected↔actual 逐行重比、G3/G4 对锁定夹具文件、golden 对 metrics_matrix 值漂移、G1 对 company_resolution、G2 对矩阵语义。[实测] 四向篡改全部拦截且诊断精确到行（`stored_status=PASS:recomputed=FAIL`、`fixture_expected_mismatch`、`metrics_value_drift:B01`）。模式判定为显式三态：证据齐全→FULL_VALIDATION（**优先于 marker**，误留 marker 无法降级完整工作区）；证据缺失+`LIGHT_REVIEW_PACKAGE.marker`→轻量模式；证据缺失无 marker→WORKSPACE_INCOMPLETE 硬失败（区分"审核者沙箱"与"工作区损坏"）。

### 5.5 防线五：多 AI 对抗审计流程（体系外的人-机制度）

代码内防线之上是流程防线：Codex 开发 → GPT 与 Claude **独立**审计 → 发现互相复现确认 → **并集**合并为修复指令 → Codex 修复 → 审计方用定制对抗测试重放验证。关键教训（第四轮实证）：两条审计流发现的缺陷集合不同，若指令只含其中一份清单，另一份的缺陷会原样存活——**修复覆盖=指令覆盖**，并集合并必须是显式流程步骤。

### 5.6 守恒律：准确性是过程不是状态

五轮演化的元规律，本项目最深的一课：**每一轮门禁都被精确满足，每一轮缺陷都迁移到门禁的下一个像素之外。**

```text
轮次  当轮门禁覆盖         被抓住的缺陷                缺陷迁移去向
─────────────────────────────────────────────────────────────────
一    仅标准数值断言       文本层有值格 100% 错值      （门禁外全域）
二    +证据支撑性          错值修了                    架构个体化（11 处公司名派发）
三    +身份字面量门禁      字面量归零                  泛化词表过拟合源公司；
                                                      源公司召回归零；探针过宽
四    +行为夹具+值域语义   过拟合修了                  阈值成分混入候选池；
                                                      断言深度（存在级 vs 值级）
五    +阈值排除+篡改回归   对抗火力全被接住            理论字缝（概率量级残余）
```

推论：质量的边界就是断言的边界，一寸不多（Goodhart 定律的工程形态——当度量成为目标，度量就不再是好度量；对策不是放弃度量，而是持续把上一轮的逃逸路径固化为下一轮的门禁）。所以"如何保证准确性"的完整答案是：五层防线 + **把每次事故转化为永久回归门禁的机制** + 承认静态防线的极限并用真实世界输入（live 试点）勘探"想不到"的空间。

---

## 6. 残余风险登记簿（截至 round3，每条含触发条件与修法）

一份让你成为专家的文档，最不可省略的就是这一节。按危险度排序：

**R1 [修订·v1.1] 10-K/A 回退：通用 full-instance 回退未完成；C04 已有局部回退。** v1.0 称"无任何回退路径"表述过强：`auditor_current_filing_candidates` 自 round3 即存在——target 为 10-K/A 时追加同报告期原始 10-K（role=auditor_current_10k）供 AuditorName 检索（[考证] 函数体已读，[实测] round3/0708 两包 grep 均在）。v1.0 漏检根源是审计 grep 的 head-8 截断吞掉了第 7817 行证据。**通用回退仍缺**（双方一致确认）：不存在"解析事实数过少时回退解析原始 10-K 完整 instance"的机制，Southwest/Paramount 型 10-K/A 的维度指标仍受影响（第一轮实证 36/117 行 vs 正常 1,200–8,400）。修法不变：`若 form==10-K/A 或解析事实数 < 500 → 定位同财年原始 10-K → 解析其完整 instance，role 标 target_original_full_instance`。扩展前**必修**。

**R2 [实测] Basel 阈值排除的裸 WellCapitalized 字缝。** 排除词表含 tobewellcapitalized/wellcapitalizedminimum 但无裸 wellcapitalized；概念名恰以 `...RatioWellCapitalized` 结尾（无 minimum/required 修饰）可穿透，端到端对决实测 0.065 能赢过实际值。us-gaap 标准命名族全部带修饰词，此缝仅银行自定义扩展可能踩中——概率量级残余。修法一行：fragment 表加裸 `wellcapitalized`（实际比率概念永不自称 well-capitalized，零误伤）。

**R3 [实测] Captive 探针成员匹配的后缀锚定召回缺口。** captive finance 指车企等的专属金融子公司（Ford Credit 型），其高杠杆会扭曲合并口径负债权益比，探针检测到即标 NEEDS_REVIEW 提示需工业/金融双口径。终版探针只对**债务概念上的分部/法人维度**触发（精度侧四象限测试全对，Enphase 的普通融资租赁不再误伤），但成员匹配用后缀锚定（endswith creditmember 等四后缀）：`FordCreditMember` 命中，而 GM 真实成员名 `GeneralMotorsFinancialCompanyIncMember`、Deere 的 `JohnDeereCapitalCorporationMember` 这类金融 token 后挂公司法尾巴的命名全部漏网。漏网后果是软的（合并值仍真实，缺的是"被扭曲"复核标注）。修法：包含匹配 + 排除守卫（含 credit|financialservices|captivefinance|financingsubsidiary|capitalcorp，排 creditloss|creditfacility|letterofcredit|lineofcredit）。

**R4 [再修订·v1.2] iXBRL scale：helper 已实现，旧“100 倍错值”归因应撤销；但端到端路由仍需硬化。** v1.0 称“scale 未处理、维度金额有 100 倍风险”过强；Claude v1.1 指出 `scaled_inline_value` 早已存在，并能处理 `value×10^scale`、`sign="-"` 与括号负数，这一点应采纳。旧文档把某个 2,948,040,000 行误归因为 JPM CET1 capital 的说法也应撤销。**但“产物正确，缺口只剩专项回归”仍过松。** 本轮合成路由测试显示：`InlineFactParser` 单独解析 `<ix:nonFraction scale="6" name="us-gaap:CommonEquityTier1Capital">294804</ix:nonFraction>` 会得到 `294804000000`；但 `parse_instance_with_fallback()` 对 well-formed inline XHTML 先走 XML streaming parser，可能输出 concept=`nonFraction`、value=`294804`，从而绕过 scale helper。当前核心 A01/A02 只消费 `pure` 比率事实，所以矩阵安全；但维度金额在用于派生指标前必须先补端到端 regression。修法：检测 inline namespace 或 `ix:nonFraction` 时直接走 inline parser，或让 XML parser 显式识别 ix facts 的 `name/contextRef/unitRef/scale/sign`；加入金额级 golden（例如 JPM CET1 capital = 294,804,000,000 @ 方法论轴）；加入 parse-route regression，断言 well-formed inline XHTML 不得被 XML 主路径错误吞掉。

**R5 [考证] FI 的 SIC 规则区间偏窄。** profile_rules 覆盖 6020–6029（国民商业银行），储蓄机构（6035/6036）、投行（6211）会静默落入 default_non_fi 丢失整个 FI 指标轨。配置层拓宽即可，registry 的 override 列是逃生舱。

**R6 [考证] FI 行为断言是概念级非值级。** 第 11 家夹具的 FI 检查断言"选中事实的概念等于期望概念"（足以咬死阈值被选中这类缺陷），但不断言选中**值**——同概念错期间/错维度的选择不会被抓。廉价升级：夹具加 expected_value 列，断言 `selected["value"]==expected`。

**R7 [实测] 住宿表格机的单元格节奏假设。** 装配步假设"绝对值/变化值交替"节奏；三年度对比表（每 KPI 三个绝对值）等异构节奏会失配——但被恒等式硬门压成诚实空手（召回损失非错值，失败等级正确）。扩展到 Hilton/Hyatt 真实年报时预期这里是主要召回瓶颈。

**R8 [实测] AST 泛化扫描器的字符串拼接盲区。** `"Ford Motor " + "Company"` 在 AST 中是两个独立常量节点，注入探针 6 种违规形态抓 5 漏此 1。当前代码无活体利用（折叠重扫为零），但通道敞开。修法：扫描器加常量折叠（遇字符串 BinOp(Add) 先求值再比对）。

**R9 [考证] 召回棘轮尚未真咬合过。** 基线快照是 round2 自身的 OK 集（形态正确：只读夹具文件、无写入路径），本轮比对等于自己比自己，第一次真实咬合在下一次有产出变化的运行。知道它"存在但未经实战"即可。

**R10 [实测·化妆级] B11 quote 的 raw_header 截取窗口从句中开始**，token 齐全但不雅观；FI 规则区间、lodging scope 词表等配置的覆盖面需随新公司持续扩充（这是设计内的常规运维，不是缺陷）。

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

静态防线只能防住"想得到的失败"；剩余风险按定义住在"想不到"里，只有真实世界能勘探。方案：Hilton（SIC 7011）、Citigroup（6021）、GM（3711）各填一行注册表，全管道真拉 SEC（成本约数百请求）。三个定向看点：Citi 的真实 Basel 标注检验阈值排除与 R2 字缝的野外存活率；Hilton 的真实表格排版检验恒等式列序自识别与 R7 节奏假设；GM 的 `GeneralMotorsFinancialCompanyIncMember` 当场裁决 R3 召回缺口。试点产出的 exceptions 清单，就是千家公司产品的第一份真实需求文档。

---

## 8. 文件地图与代码阅读路径

```text
scripts/
  sec_pipeline.py        全部逻辑单体（~10,500 行）。阅读入口见下。
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
  test_sec_pipeline_validation.py    7 个篡改回归单元测试
outputs/   （每个 CSV 的 schema 在 03 号指令文档第 6 节）
  metrics_matrix.csv     主交付物：230 行六件套
  metric_evidence.csv    证据明细（quote/原文/解析方法）
  coverage_matrix.csv    每格的通路与可得性归因
  golden_results.csv     57 条断言结果
  repair_validation_results.csv   38 项门禁结果
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

## 9. 术语表

```text
spike              为验证可行性的一次性探索开发
accession          SEC 申报唯一编号（如 0001463101-26-000013）
10-K / 10-K/A      年报 / 年报修正案
8-K / DEF 14A      重大事项即时报告 / 股东大会委托书
XBRL / iXBRL       财务事实标签化标准 / 其嵌入 HTML 的内联形态
concept            事实的语义标签名；us-gaap=标准分类账，公司域名=自定义扩展
dimension          轴(axis)+成员(member)构成的事实限定
unit: pure / USD   纯数（比率）/ 美元金额
scale              iXBRL 数字的 10 幂缩放声明；helper 已实现，但 parse route 与
                   金额类消费仍需端到端 regression，见 R4
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
GO / GO WITH CAVEATS / NO-GO        管道自评 verdict（01 号 SOP 的 M7 定义，写在 REPORT 里）
ACCEPT / ACCEPT WITH CAVEATS / REJECT  外部验收 verdict（04 号清单定义，由审计方出具）
                   两套词汇属于不同层级，不应合并：自评与外审的分歧本身是
                   诊断信号——round2 的 stratified FAIL vs 报告 GO WITH CAVEATS
                   正是靠这个分层才被定性为"门禁没接上"而非数据错误
```


---


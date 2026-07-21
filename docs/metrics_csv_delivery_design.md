# SEC 指标结果 CSV 拆分与交付方案

状态：建议方案，尚未实施

适用范围：当前 SEC-only、单财年批处理输出

目标读者：业务负责人、数据交付负责人、开发与 reviewer

## 1. 结论

当前 `outputs/metrics_matrix.csv` 不宜继续通过增加列来承载所有结果、方法、来源与说明。建议将其拆为四个同构的主结果 CSV，并继续使用一个统一的逐条证据 CSV：

```text
outputs/
├── financial_metrics.csv
├── governance_signals.csv
├── risk_legal_signals.csv
├── event_signals.csv
├── metric_evidence.csv
├── metrics_all.csv                  # 自动合并的便利文件，非独立真相源
└── metrics_data_dictionary.md       # 实施后从本方案派生的数据字典
```

文件边界如下：

| 文件 | 指标范围 | 主要用途 |
|---|---|---|
| `financial_metrics.csv` | `Axx`、`Bxx` | 金融机构、一般企业财务及行业经营指标 |
| `governance_signals.csv` | `Cxx` | 治理、领导层、薪酬与审计师信号 |
| `risk_legal_signals.csv` | `Dxx` | 风险、诉讼、监管与持续经营定性信号 |
| `event_signals.csv` | `Exx` | 财年窗口内的 8-K 事件计数与扫描结果 |
| `metric_evidence.csv` | 全部指标 | 一条结果所依赖的逐条事实、文本或扫描覆盖证据 |
| `metrics_all.csv` | 前四个文件的合集 | 兼容需要单文件消费的场景，只能自动生成 |

四个主结果文件使用完全相同的列结构，既可单独读取，也可安全纵向合并。来源 accession、form、filed date、concept、context 和原文证据不再塞进主结果单元格，而是统一写入 `metric_evidence.csv`。

本方案不改变当前项目已经实现的事实。完成代码、验证和文档迁移前，现有 `metrics_matrix.csv` 仍是当前流水线产物。

## 2. 设计原则

1. 一个 CSV 只承担一种稳定业务用途。
2. 主结果文件保留“结果是什么、状态如何、覆盖什么期间”；来源细节进入 evidence。
3. 四个主结果文件同构，避免四套读取和校验逻辑。
4. 不在单元格中继续累积多 accession、多日期、多 concept 或多 context。
5. 空值、零值、定性结果和不可用状态必须保持不同语义。
6. 公司、指标和 evidence 使用稳定可重复的关联标识。
7. 便利汇总文件只能由权威文件自动生成，不能人工维护。
8. 继续复用已有权威定义，避免为了拆 CSV 再制造一套漂移的真相源。

## 3. 为什么采用“4 个业务结果文件 + 1 个 evidence 文件”

当前矩阵同时容纳四种明显不同的结果：

- `Axx/Bxx` 主要是 USD、ratio、percent 等数值财务或行业指标；
- `Cxx` 可能是 count、flag、USD，也可能只有治理文本结论；
- `Dxx` 多数是 `TEXT_QUAL` 定性结果；
- `Exx` 是财年窗口事件计数，零值可能表示“完整扫描后未命中”。

当前快照共有 230 行、10 个逻辑公司和 39 个指标。`(company, metric_id)` 在当前快照中唯一，但 10 个逻辑公司对应 11 个实际 CIK，说明 CIK 是来源实体身份，不能简单等同于逻辑公司身份。

最影响维护的不是行数，而是来源字段的复合值：当前 `accession` 有大量分号拼接行，`filed_date` 和 `context_or_dimension` 也存在多值。继续扩充一个总矩阵会同时放大以下问题：

- 人工阅读困难；
- 多值字段无法稳定对应；
- 结果、方法和来源职责混杂；
- 事件零值和普通数值零容易被误用；
- 新增长文本字段会使每条结果越来越宽。

按业务范围拆四个主结果文件，可以让不同使用者直接拿到所需主题；保持相同列结构，则避免文件拆分造成额外技术复杂度。逐条来源继续集中到已有 `metric_evidence.csv`，避免再创建重复的 `metric_sources.csv`。

## 4. 不新增两套默认权威目录

### 4.1 公司定义继续来自 registry

逻辑公司、主 CIK、ticker、SIC、行业 profile、财年末和实体连续性继续以 `config/company_registry.csv` 为权威来源。主结果文件新增 `company_id`，其值直接来自 registry。

默认不再维护一份内容重复的权威 `company_catalog.csv`。如果外部交付只能接收 `outputs/`，可以从 registry 自动派生 `outputs/company_catalog.csv`，但该文件仍是派生产物。

### 4.2 指标定义继续来自现有指标定义文档

每个指标的业务定义、候选链、公式、适用性和降级规则继续以 `02_指标定义_SEC_10公司单年指标.md` 及实现/validation 为准。

默认不新增手工维护的权威 `metric_catalog.csv`。结构化消费者确有需要时，可以从指标定义和配置自动派生，但不能让它与现有定义文档分别维护。

## 5. 四个主结果文件

### 5.1 文件范围

#### `financial_metrics.csv`

包含：

- `Axx`：金融机构指标；
- `Bxx`：一般企业财务、偿债、流动性及行业经营指标。

A 和 B 都符合“公司 + 指标 + 期间 + 数值/状态”的主要结果形态。A 类当前主要适用于 JPMorgan，若再单独拆文件会形成过小且稀疏的结果集，因此合并为一个财务文件。

#### `governance_signals.csv`

只包含 `Cxx`：

- `C01` CEO / CFO changes；
- `C02` Board composition；
- `C03` Executive compensation signals；
- `C04` Auditor changes。

治理结果中的状态和结论可能比数值更重要，来源主要为 DEF 14A、8-K 和 accession instance。

#### `risk_legal_signals.csv`

只包含 `Dxx`：

- `D01` Risk factors summary；
- `D02` Litigation disclosures；
- `D03` Regulatory investigations；
- `D04` Going concern statements。

这类结果通常为定性结论，必须区分“找到定性证据”“SEC 范围内未披露”“未可靠抽取”和“解析失败”。

#### `event_signals.csv`

只包含 `Exx`：

- `E01` M&A announcements；
- `E02` Bankruptcy filings；
- `E03` Leadership departures；
- `E04` Financial restatements；
- `E05` Material agreements。

事件结果的 `period_start` 和 `period_end` 表示扫描窗口，`value` 表示窗口内命中数量。`value=0` 且 `status=NOT_AVAILABLE_SEC` 表示在已定义扫描范围内未命中，不能改写成普通 `OK` 零值。

### 5.2 统一列结构

四个主结果文件统一使用以下 17 列：

```text
result_key
company_id
company
cik
metric_id
metric_name
value
unit
status
source_class
result_method
period_start
period_end
fiscal_year
fiscal_period
confidence
result_note
```

### 5.3 主结果字段字典

| 字段 | 含义 | 规则与注意事项 |
|---|---|---|
| `result_key` | 结果记录的稳定关联标识 | 连接主结果与 evidence；同一交付批次内必须唯一 |
| `company_id` | registry 中的稳定逻辑公司代码 | 例如 `marriott_international` |
| `company` | 公司展示名称 | 保留以便直接阅读；身份关联优先使用 `company_id` |
| `cik` | 本条结果实际使用的 SEC CIK | 保存为补齐 10 位的字符串；不等同于逻辑公司唯一主键 |
| `metric_id` | 指标代码 | 例如 `B01`、`C04`、`E02`；前缀必须与所在文件匹配 |
| `metric_name` | 指标展示名称 | 与指标定义中的名称保持一致 |
| `value` | 结果值 | 没有可靠数值时为空；空值绝不能自动改为零 |
| `unit` | 结果单位 | `USD`、`ratio`、`pure`、`percent`、`count`、`flag` 或空值 |
| `status` | 结果状态 | 表示数值可用性、定性、缺失、不适用或待复核语义 |
| `source_class` | 主要来源类别 | 表示本条结果的主来源或形成方式 |
| `result_method` | 本条结果的计算或抽取方式 | 由当前 `formula` 迁移；可为公式、`direct`、文本抽取或事件扫描 |
| `period_start` | 期间或扫描窗口开始日期 | ISO `YYYY-MM-DD`；时点指标可与 `period_end` 相同 |
| `period_end` | 期间、时点或扫描窗口结束日期 | ISO `YYYY-MM-DD`；当前主结果必须非空 |
| `fiscal_year` | 流水线保留的 SEC 财年标签 | 允许为空；不能作为唯一期间标识 |
| `fiscal_period` | 财务期间标签 | 通常为 `FY`，允许为空 |
| `confidence` | 当前抽取或选择置信度 | 0 至 1；不是统计概率或外部审计结论，不能覆盖 `status` |
| `result_note` | 结果级简短说明 | 只保留口径、结论、限制或复核提示；原始来源细节进入 evidence |

### 5.4 `result_key` 规则

建议使用可读、可重复生成的组合键：

```text
company_id|cik|metric_id|period_start|period_end
```

示例：

```text
marriott_international|0001048286|B01|2025-01-01|2025-12-31
```

规则：

1. CIK 固定为 10 位字符串；
2. 日期固定为 ISO 格式；
3. 缺失的 `period_start` 使用空字符串，不另造日期；
4. 同一批次四个主结果文件中 `result_key` 全局唯一；
5. 如果未来同一结果需要保存多个运行版本，再在所有相关文件统一增加 `batch_id`，不在本次拆分中提前引入复杂版本模型。

## 6. `metric_evidence.csv` 的目标结构

### 6.1 粒度

目标粒度是：

> 一行代表一个结果所使用的一个来源事实、公式组件、文本证据或扫描覆盖记录。

当前 evidence 已有来源 URL、路径、accession、document、concept、context、原始值、归一化值、证据说明、抽取方法和 parser version。拆分时主要是增强关联和单值约束，而不是新建一套重复来源文件。

### 6.2 建议字段

```text
evidence_id
result_key
evidence_role
source_seq
company_id
company
cik
metric_id
source_class
source_url
relative_path
accession
form
filed_date
document_name
concept_or_section
context_or_dimension
unit
period_start
period_end
value_raw
value_normalized
evidence_quote
extraction_method
parser_version
```

### 6.3 Evidence 字段字典

| 字段 | 含义 | 规则与注意事项 |
|---|---|---|
| `evidence_id` | 单条证据唯一标识 | 可由 `result_key + source_seq` 稳定生成 |
| `result_key` | 对应的主结果 | 必须能匹配四个主结果文件中的一条记录 |
| `evidence_role` | 证据在结果中的作用 | 仅使用本节规定的四个枚举 |
| `source_seq` | 同一结果下的证据顺序 | 从 1 开始，和 `evidence_id` 一起保证稳定性 |
| `company_id` | 稳定逻辑公司代码 | 来自 registry |
| `company` | 公司展示名称 | 与主结果一致 |
| `cik` | 该证据对应的 SEC CIK | 10 位字符串；允许与逻辑公司的 primary CIK 不同 |
| `metric_id` | 对应指标 | 与主结果一致 |
| `source_class` | 该条证据的来源类别 | 结果层保存主要来源，evidence 层保存具体来源 |
| `source_url` | SEC 官方来源 URL | 生产来源继续限定为官方 SEC 域名 |
| `relative_path` | 仓库或 evidence 包内相对路径 | 替代不可移植的历史绝对 `local_path` |
| `accession` | 单个 SEC accession | 禁止继续在同一格中分号拼接多个 accession |
| `form` | 单个 filing form | 例如 `10-K`、`8-K`、`DEF 14A` |
| `filed_date` | 单个 filing 的提交日期 | ISO `YYYY-MM-DD` |
| `document_name` | 文档或证据文件名称 | 保留具体来源定位信息 |
| `concept_or_section` | 单个 concept、章节或 item | 派生指标的多个 concept 拆为多条 component evidence |
| `context_or_dimension` | 单个 context、dimension 或文本范围 | 不再用分号承载多条来源 |
| `unit` | 来源事实单位 | 可能与最终结果单位不同 |
| `period_start` | 来源事实期间开始 | ISO 日期，允许为空 |
| `period_end` | 来源事实期间结束 | ISO 日期 |
| `value_raw` | 来源原始值 | 保留原始表达，不覆盖 |
| `value_normalized` | 流水线归一化值 | 与结果计算口径对应 |
| `evidence_quote` | 文本片段、表格行或公式组件说明 | 遵守现有证据要求 |
| `extraction_method` | 抽取方法 | 例如 `companyfacts_direct`、`companyfacts_derived`、文本抽取或事件扫描 |
| `parser_version` | 生成证据的 parser 版本 | 用于复核生成逻辑 |

### 6.4 `evidence_role` 枚举

| 值 | 含义 |
|---|---|
| `PRIMARY` | 直接产生最终结果的主要来源 |
| `COMPONENT` | 派生指标的一个计算组件 |
| `TEXT_SUPPORT` | 支撑治理、风险或法律判断的文本证据 |
| `SCAN_COVERAGE` | 证明某个 filing 已纳入事件扫描，即使未命中事件 |

暂不增加更多角色。无法归入这四类的场景应先复核数据粒度，而不是立即扩展枚举。

## 7. 当前 `metrics_matrix.csv` 完整字段字典与迁移映射

### 7.1 全量字段字典

下表逐列解释当前 `outputs/metrics_matrix.csv` 的全部 20 个字段。这里说明的是字段本身的业务含义、当前内容格式、典型值和空值语义，不是数据库类型，也不是后续拆分后的新字段。当前值和数量基于本方案编写时的 230 行快照，重跑批次后可能变化。

| 序号 | 列名 | 中文含义 | 内容与格式 | 当前值或例子 | 空值与使用注意事项 |
|---:|---|---|---|---|---|
| 1 | `company` | 逻辑公司展示名称 | UTF-8 文本；当前有 10 个逻辑公司 | `Marriott International`、`JPMorgan Chase`、`Paramount Skydance / Paramount Global` | 当前无空值。它是展示名称，不是稳定技术 ID；Paramount 名称还表达 successor/predecessor 逻辑连续性 |
| 2 | `cik` | 本条结果实际使用的 SEC registrant CIK | 当前 CSV 保存未补零的数字字符串；当前有 11 个不同 CIK | `1048286`、`92380`、`2041610`、`813828` | 当前无空值。不能把它直接当作逻辑公司唯一键；同一逻辑公司可能因实体连续性使用不同 CIK |
| 3 | `metric_id` | 指标稳定代码 | 形如 `A01` 至 `E05`；首字母表示指标类别；当前有 39 个代码 | `A01`、`B03`、`C04`、`D02`、`E05` | 当前无空值。A=金融机构，B=一般财务/行业，C=治理，D=风险法律，E=事件 |
| 4 | `metric_name` | 指标英文展示名称 | UTF-8 文本；与 `metric_id` 一一对应；当前有 39 个名称 | `Revenue`、`EBITDA margin`、`Auditor changes` | 当前无空值。用于阅读，不应脱离 `metric_id` 单独作为稳定关联字段；具体口径以指标定义文档为准 |
| 5 | `value` | 指标输出值 | CSV 中为文本表达的整数或高精度小数，可为负数 | `26186000000`、`0.04326693227091633466135458167`、`0` | 当前 69 行为空。空值不等于 0，必须结合 `status`；事件行的 0 还要区分命中为零与完整扫描未命中 |
| 6 | `unit` | `value` 的业务单位 | 枚举：`USD`、`ratio`、`pure`、`percent`、`count`、`flag` 或空值 | `USD`、`ratio`、`percent` | 当前 64 行为空，通常对应定性、缺失或不适用结果。`ratio/pure` 使用小数表达，`percent` 使用百分数值，详细语义见 8.3 |
| 7 | `status` | 结果状态和可用性语义 | 代码允许 13 个枚举；当前快照出现 12 个 | `OK`、`TEXT_QUAL`、`NOT_AVAILABLE_SEC`、`NEEDS_REVIEW` | 当前无空值。不能折叠为简单成功/失败，也不能只根据 `value` 是否为空推断状态；完整定义见 8.1 |
| 8 | `source_class` | 结果的主要来源类别或形成方式 | 定义 9 个枚举；当前快照出现 8 个，未出现 `CUSTOM_XBRL` | `STD_XBRL`、`DERIVED`、`MDA`、`8K_ITEM`、`TEXT` | 当前无空值。它回答“主要从哪里来或怎样形成”，不回答结果是否可采信；必须与 `status` 一起阅读，完整定义见 8.2 |
| 9 | `formula` | 本条结果实际使用的计算公式或抽取方法 | 自由文本；当前有 15 种表达 | `direct`、`(Revenue_t - Revenue_t-1) / Revenue_t-1`、`text/event extraction` | 当前无空值，但可能是 `not numeric in companyfacts stage` 等占位方法说明。它不是指标标准定义的唯一真相源 |
| 10 | `period_start` | 结果覆盖期间或扫描窗口的开始日期 | ISO `YYYY-MM-DD`；时点型结构化事实通常将开始日写成与结束日相同 | `2025-01-01`、`2025-12-31`、`2025-02-01` | 当前 2 行为空。为空表示当前结果没有可靠开始日，不能自行用自然年初补齐 |
| 11 | `period_end` | 结果覆盖期间、时点或扫描窗口的结束日期 | ISO `YYYY-MM-DD`；当前有 3 个不同日期 | `2025-12-31`、`2026-01-31`、`2024-12-31` | 当前无空值。它是当前文件最稳定的时间切片字段，但不同公司财年末和特殊连续性期间不可混为同一自然年 |
| 12 | `fiscal_year` | 命中结构化 companyfacts 时保留的 SEC `fy` 标签 | 年份文本；当前非空值只有 `2025` | `2025` | 当前 150 行为空，主要是文本、治理、事件和特殊抽取。不能用它替代 `period_start/period_end`，也不能把空值理解为无报告期间 |
| 13 | `fiscal_period` | SEC `fp` 财务期间标签 | 短文本；当前非空值为 `FY` | `FY` | 当前 9 行为空。为空表示该抽取路径没有可靠 `fp`，并不自动表示非年度结果 |
| 14 | `accession` | 支撑本条结果的 SEC accession number | 单个 accession，或当前旧结构中的分号拼接列表 | `0001048286-26-000007`、`0001048286-26-000007;0001628280-25-004818` | 当前 3 行为空，111 行含分号。多个 accession 不保证能与其他复合字段按位置一一对应；拆分后应进入逐条 evidence |
| 15 | `form` | 主要来源 filing 的表单类型 | 当前矩阵中为 `10-K` 或空值 | `10-K` | 当前 146 行为空。空值不代表没有 SEC 来源；很多 DEF 14A、8-K、MDA、TEXT 或修复路径没有在该汇总列重复 form |
| 16 | `filed_date` | 支撑来源的 SEC filing 提交日期 | 单个 ISO 日期，或当前旧结构中的分号拼接列表 | `2026-02-10`、`2026-02-10;2025-02-11` | 当前 15 行为空，105 行含分号。它不是单值日期字段，拆分时应与具体 evidence/accession 绑定，不能只取第一项或最后一项 |
| 17 | `concept_or_section` | 结构化 concept、多个计算组件，或文本章节/8-K item | 自由文本；多个 XBRL 组件当前常用 `+` 连接 | `Revenues`、`AssetsCurrent+LiabilitiesCurrent`、`Item 1A Risk Factors` | 当前 6 行为空。同一单元格可能表示 concept 列表，也可能表示章节名称，解释时必须结合 `source_class` 和 `formula` |
| 18 | `context_or_dimension` | XBRL frame/context/dimension，或文本/扫描范围 | 自由文本；当前可能使用分号连接多个 context | `companyfacts:USD:CY2025`、`proxy statement`、`FY-window 8-K accessions scanned` | 当前 15 行为空，57 行含分号。不同来源类型的内容结构不同，不能将它当成统一维度代码直接解析 |
| 19 | `confidence` | 流水线对本次抽取、选择或判断赋予的置信度 | 0 至 1 的小数字符串；当前范围为 `0.00` 至 `0.95` | `0.95`、`0.90`、`0.65`、`0.00` | 当前无空值。它是方法级提示，不是统计概率、审计接受或投资置信度；`status` 的限制优先于高 confidence |
| 20 | `notes` | 结果级口径、假设、限制、候选事实及复核说明 | UTF-8 自由文本，可能较长 | `Revenue candidate chain from metric definition.` | 当前无空值。分号可能只是自然语言标点或组件说明，不能按分号机械拆列；采信结果前应阅读相关限制 |

### 7.2 迁移映射

| 当前字段 | 新位置 | 迁移规则 |
|---|---|---|
| `company` | 四个主结果 + evidence | 保留；同时从 registry 补 `company_id` |
| `cik` | 四个主结果 + evidence | 保留并补齐为 10 位字符串；表示实际来源实体 |
| `metric_id` | 四个主结果 + evidence | 保留；按前缀路由到对应主结果文件 |
| `metric_name` | 四个主结果 | 保留，方便单文件直接阅读 |
| `value` | 四个主结果 | 保留；空值语义由 `status` 决定 |
| `unit` | 四个主结果 + evidence | 结果层保存结果单位，evidence 层保存来源单位 |
| `status` | 四个主结果 | 原样保留，不折叠状态 |
| `source_class` | 四个主结果 + evidence | 结果层保存主要来源；evidence 保存逐条具体来源 |
| `formula` | 四个主结果的 `result_method` | 财务行保存公式；其他行保存抽取或扫描方法 |
| `period_start` | 四个主结果 + evidence | 结果期间与来源期间分别保存 |
| `period_end` | 四个主结果 + evidence | 结果期间与来源期间分别保存 |
| `fiscal_year` | 四个主结果 | 保留，允许为空 |
| `fiscal_period` | 四个主结果 | 保留，允许为空 |
| `accession` | evidence | 拆为单 accession 行，不在结果文件保留复合值 |
| `form` | evidence | 与单个 accession 对应 |
| `filed_date` | evidence | 与单个 accession 对应 |
| `concept_or_section` | evidence | 一个 concept、章节或 item 一行 |
| `context_or_dimension` | evidence | 一个 context、dimension 或文本范围一行 |
| `confidence` | 四个主结果 | 保留 |
| `notes` | 四个主结果的 `result_note` + evidence | 结果层只留简短结论/限制；来源原文和组件细节进入 evidence |

迁移不能只按分号位置机械拆分现有单元格，因为 accession、日期、concept 和 context 的数量不一定一一对应。应从生成阶段的结构化事实、事件和文本对象直接写出 evidence 行。

## 8. 枚举数据字典

### 8.1 `status`

| 状态 | 含义 | value 使用规则 |
|---|---|---|
| `OK` | 标准或直接可采信结果 | 通常应有非空数值和 matching evidence |
| `OK_APPROX` | 有明确近似口径 | 应有数值；必须阅读 `result_method` 和 `result_note` |
| `DIM_XBRL_OK` | 来自维度 XBRL 事实 | 数值或 flag 应有逐条 evidence |
| `MDA_OK` | 来自 MD&A 或表格文本 | 数值应有表头/原始行证据 |
| `DEF14A_OK` | 来自 DEF 14A 或 ecd XBRL | 数值应有对应 filing evidence |
| `8K_ITEM_OK` | 来自 8-K item 或事件规则 | value 通常为事件计数 |
| `TEXT_QUAL` | 有定性证据，无精确数值 | value 通常为空，但结果仍有业务意义 |
| `NOT_AVAILABLE_SEC` | 在已定义 SEC 范围内未找到披露或事件 | 事件扫描可保存 0，但不是普通 `OK` 零值 |
| `NOT_EXTRACTED` | 可能有披露，但当前未可靠抽取 | value 应为空 |
| `PARSE_FAILED` | 预期可解析但解析失败 | value 应为空并保留诊断 |
| `NEEDS_REVIEW` | 存在候选、冲突或复杂口径 | 人工复核前不能升级为正常可用结果 |
| `NOT_MEANINGFUL` | 数字可能存在，但当前经济或连续性语境下无可靠意义 | 主 value 通常为空 |
| `N_A_STRUCTURAL` | 指标对该行业或主体结构不适用 | value 应为空 |

### 8.2 `source_class`

| 值 | 含义 |
|---|---|
| `STD_XBRL` | SEC Company Facts 标准公司级事实 |
| `DIM_XBRL` | accession instance 中的维度事实 |
| `CUSTOM_XBRL` | accession instance 中的公司自定义事实 |
| `MDA` | MD&A 或 EX-99 表格/文本 |
| `DEF14A` | DEF 14A、ecd XBRL 或委托书文本 |
| `8K_ITEM` | 8-K item 或财年窗口事件扫描 |
| `TEXT` | 10-K、10-Q 或 8-K 文本章节 |
| `DERIVED` | 由多个事实计算得到 |
| `NOT_AVAILABLE` | 没有可用来源或未找到可靠事实 |

### 8.3 `unit`

| 值 | 含义 | 示例解释 |
|---|---|---|
| `USD` | 美元金额 | `26186000000` 表示 26,186,000,000 美元 |
| `ratio` | 小数比例或倍数 | `0.0433` 表示约 4.33%；大于 1 时也可能表示倍数 |
| `pure` | XBRL 无量纲小数 | `0.155` 表示 15.5% 的无量纲比率 |
| `percent` | 已按百分数表达的值 | `69.3` 表示 69.3%，不是 0.693 |
| `count` | 数量或事件次数 | `0` 需结合 `status` 判断语义 |
| `flag` | 0/1 标志 | 具体真假含义由指标定义和 `result_note` 说明 |
| 空值 | 没有数值表达 | 常见于定性、缺失、不适用或待复核结果 |

## 9. 三个典型拆分示例

### 9.1 派生财务指标：Marriott B03 EBITDA margin

`financial_metrics.csv` 保存一条结果：

```text
result_key   = marriott_international|0001048286|B03|2025-01-01|2025-12-31
metric_id    = B03
value        = 0.175628...
unit         = ratio
status       = OK
result_method = (Operating income + D&A) / revenue
```

`metric_evidence.csv` 保存多个 `COMPONENT` 行，例如：

```text
OperatingIncomeLoss
Depreciation
AmortizationOfIntangibleAssets
Revenues
```

不再在一个结果单元格中保存 `OperatingIncomeLoss+Depreciation+AmortizationOfIntangibleAssets+Revenues`。

### 9.2 定性风险结果：D04 Going concern

`risk_legal_signals.csv`：

```text
metric_id    = D04
value        =
status       = TEXT_QUAL
source_class = TEXT
result_note  = No going-concern doubt phrase found in 10-K text.
```

`metric_evidence.csv` 保存 filing、章节、文本范围和 evidence quote。空 value 不表示记录无用，`TEXT_QUAL` 明确说明它是定性结论。

### 9.3 事件零值：E02 Bankruptcy filings

`event_signals.csv`：

```text
metric_id    = E02
value        = 0
unit         = count
status       = NOT_AVAILABLE_SEC
period_start = 2025-01-01
period_end   = 2025-12-31
result_note  = No Item 1.03 found in the defined fiscal-year scan window.
```

`metric_evidence.csv` 为扫描过的 filing 保存 `SCAN_COVERAGE` 行。这样可以验证零值表示“既定窗口内未命中”，而不是缺数据或事件绝对不存在。

## 10. `metrics_all.csv` 与 `metrics_matrix.csv`

### 10.1 `metrics_all.csv`

`metrics_all.csv` 是四个主结果文件的自动纵向合并：

```text
financial_metrics
+ governance_signals
+ risk_legal_signals
+ event_signals
= metrics_all
```

要求：

- 列名和列顺序与四个主结果文件完全一致；
- 行数等于四个文件行数之和；
- 不允许在 `metrics_all.csv` 单独修改任何记录；
- 重跑后完全由主结果重新生成。

### 10.2 现有 `metrics_matrix.csv` 的过渡定位

拆分不能直接删除或静默改写当前 `metrics_matrix.csv`，因为当前报告、validation、文档和消费者依赖它。建议分阶段迁移：

1. 新增四个主结果文件和增强后的 evidence，同时保留现有 matrix；
2. 为新旧输出增加等价性检查；
3. 更新报告、coverage、Golden、repair validation、文档和消费者；
4. 完成切换后，将 `metrics_matrix.csv` 明确为兼容别名，或由 `metrics_all.csv` 取代；
5. 任何移除决定都必须同步更新能力契约、用户行为、架构与测试文档。

在第 4 步完成前，不得把规划中的新文件描述为当前已实现产物。

## 11. 跨文件不变量与验收规则

### 11.1 主结果文件

1. 四个文件列结构完全一致。
2. `financial_metrics.csv` 只允许 `A`、`B` 前缀。
3. `governance_signals.csv` 只允许 `C` 前缀。
4. `risk_legal_signals.csv` 只允许 `D` 前缀。
5. `event_signals.csv` 只允许 `E` 前缀。
6. `result_key` 在四个文件合集内唯一。
7. `company_id` 必须存在于 company registry。
8. `metric_id`、`metric_name` 和适用性必须符合指标定义与配置。
9. `period_end` 必须非空，日期统一为 ISO 格式。
10. CIK 必须按字符串处理并补齐 10 位。
11. value 为空时必须有明确 status；不得猜数填满。
12. 可采信的非空数值必须存在 matching evidence。
13. `NOT_AVAILABLE_SEC + count + 0` 必须有 `SCAN_COVERAGE` evidence。
14. 主结果中不得出现 accession、filed date、concept 或 context 复合列。

### 11.2 Evidence 文件

1. 每条 evidence 的 `result_key` 必须匹配一个主结果。
2. `(result_key, source_seq)` 和 `evidence_id` 必须唯一。
3. accession、form、filed date、concept 和 context 应保持单值粒度。
4. 路径使用仓库内相对地址；历史绝对地址不能作为跨机器权威定位。
5. SEC URL、accession、period、concept/section 和 evidence quote 必须足以复核来源。
6. 派生指标的组成事实使用 `COMPONENT`，不能只保留最终公式字符串。
7. 定性判断使用 `TEXT_SUPPORT`。
8. 事件未命中零值使用 `SCAN_COVERAGE` 证明扫描范围。

### 11.3 汇总文件

1. `metrics_all.csv` 行数等于四个主结果文件之和。
2. 合并后 `result_key` 仍然唯一。
3. `metrics_all.csv` 与四个主结果在所有字段上逐行一致。
4. 汇总文件只能生成，不能人工编辑。

## 12. 实施顺序建议

### 阶段 1：并行生成，不改变现有消费者

- 为每条结果补 `company_id`、标准化 CIK 和 `result_key`；
- 从同一内存结果集按 metric 前缀生成四个主结果文件；
- 生成 `metrics_all.csv`；
- 保持当前 `metrics_matrix.csv` 不变；
- 增加新旧输出的行数、键和值等价检查。

### 阶段 2：规范 evidence 粒度

- 增加 `evidence_id`、`result_key`、`evidence_role`、`source_seq`；
- 增加 `company_id`、`source_class`、`form` 和 `filed_date`；
- 将可拆的派生组件和事件扫描覆盖改为一证据一行；
- 将绝对 `local_path` 改为或补充 `relative_path`；
- 不对旧复合字段做不可靠的位置拆分，从结构化生成对象直接写新行。

### 阶段 3：切换权威消费者

- 更新报告和 coverage 读取逻辑；
- 更新 Golden、repair validation、stratified audit 和 scenario tests；
- 更新 `architecture.md`、`capability_contract.json`、`interact.md`、`TESTING.md`、`README_RUN.md` 和业务指南；
- 与数据消费者完成并行核对后，再决定 `metrics_matrix.csv` 的兼容期限。

## 13. 明确不采用的拆分方式

以下条件是查询或导出条件，不是稳定的权威文件边界：

```text
每家公司一个 CSV
每个年度一个 CSV
每个 status 一个 CSV
每个 source_class 一个 CSV
每个 metric_id 一个 CSV
```

也不建议再将 `Axx` 和 `Bxx` 分开：A 类当前公司数量少，两者结果形态相同，分开只会增加稀疏小文件和重复校验。

## 14. 可选项，而非默认范围

以下文件只在外部交付确有需要时自动派生，不作为本次默认权威输出：

- `company_catalog.csv`：当消费者无法读取 `config/company_registry.csv` 时生成；
- `metric_catalog.csv`：当消费者需要结构化指标目录时从指标定义与配置生成；
- 业务展示型宽表：只能从四个主结果文件派生，不参与流水线真相判定。

不要手工维护这些可选文件，也不要让它们自行扩展公司身份、指标口径或能力承诺。

## 15. 决策摘要

最终建议控制在五个权威数据文件：

```text
财务结果
治理结果
风险法律结果
事件结果
统一证据
```

公司定义继续复用 registry，指标定义继续复用现有指标定义文档。`metrics_all.csv` 和数据字典属于自动派生的便利交付物。

这套方案吸收了两类建议的优点：

- 使用业务域拆分，解决财务、定性风险和事件结果长期混放的问题；
- 使用统一列结构和统一 evidence，避免文件拆分演变成多套互不兼容的数据格式；
- 不默认增加重复的公司/指标权威目录，控制文件数量和维护成本；
- 保留稳定关联键、清晰字段字典、过渡步骤和跨文件验收规则，确保拆分后仍可审计和自动合并。

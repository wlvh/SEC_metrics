# CIK 映射与公司身份变更应对方案

> 2026-07-17
> 适用范围：SEC 公司身份解析、Company Facts 财务指标计算、8-K 事件抽取与历史数据留存。
> 核心目标：区分“SEC filer 身份”“逻辑分析公司”和“财务可比性”，避免因为名称、ticker 或 CIK 关系而错误合并财务数据。

## 1. 核心结论

1. **CIK 不会因为公司简单更名而改变。**CIK 是 SEC 为 filer 分配的永久标识，不能修改、不会过期、不会回收；同一 CIK 可以对应多个历史名称。[SEC 对 CIK 的官方说明](https://www.sec.gov/submit-filings/filer-support-resources/how-do-i-guides/understand-utilize-edgar-cik-cik-confirmation-code-ccc)，[SEC EDGAR 数据说明](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)。
2. **Ticker 是证券与交易所层面的可变关联，不是公司主键。**Ticker 可以随更名、重组、换板或证券类别变化而改变，也可能在公司更名后保持不变。SEC 不保证 ticker/CIK/exchange 关联文件的准确性或覆盖范围。
3. **旧 CIK 数据应保留，但默认不参与当前 CIK 的标准财务指标计算。**留存是数据治理问题，计算是口径问题。
4. **同一 `company_id` 只表示经过确认的逻辑公司或继任链，不表示不同 CIK 的财务数据可以直接合并。**
5. **标准财务指标必须只有一个 `calculation_cik`。**跨 CIK 默认禁止同比；取不到安全比较期时，应输出明确状态，而不是从 predecessor CIK 强行补数。
6. **8-K 可以跨 role CIK 检索，但是否跨 CIK 聚合必须由具体事件指标决定。**检索范围不等于聚合范围。

## 2. 术语与身份层次

### 2.1 SEC filer 身份

由 CIK 表示。CIK 精确匹配是确认 SEC filer 的主要依据。

SEC submissions API 提供 current name、former names、ticker 和 exchange 等元数据；这些字段用于解释和校验身份历史，不替代 CIK。[SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)。

### 2.2 逻辑分析公司

由项目内部的 `company_id` 表示。当前项目将它定义为“一行代表一个逻辑分析公司”，而不是 SEC filer account、公司名称或 ticker。

`company_id` 是否延续，取决于项目是否确认新旧主体属于同一条业务或申报继任链，不能仅根据 CIK、名称或 ticker 自动决定。

### 2.3 展示名称和名称历史

- `display_name`：当前面向用户展示的名称，可以变化。
- `submissions.formerNames`：SEC 返回的外部元数据。
- `company_name_history`：未来可选的本地可审计名称历史，不是当前 `company_registry.csv` 的现有字段。

### 2.4 Ticker

Ticker 只表示证券与交易所的关联。一个 CIK 可能对应多个证券类别和 ticker，也可能没有 ticker。

Ticker 只能作为身份发现信号或展示属性，不能用于拼接公司历史、Company Facts 或 filing。

### 2.5 Filing 身份

一份 SEC filing 由 CIK 和 accession 共同定位。指标和事件必须保留来源 CIK、accession、form、filed date 和报告期间，不能只保留公司名称。

## 3. 身份匹配规则

身份匹配按以下优先级执行：

```text
CIK 精确匹配
→ SEC submissions.current name / formerNames 校验
→ accession 和 filing 内容确认具体事件
→ ticker 只作辅助信号
```

自动化边界：

| 匹配情况 | 系统动作 |
|---|---|
| CIK 精确相同，只有 current/former name 变化 | 可以判定为同一 filer |
| 只有 former name 相同或相近 | 只生成候选，不自动合并 |
| 只有 ticker 相同 | 只生成候选，不自动合并 |
| 新旧 CIK 且有明确 succession 文件 | 进入继任关系审核 |
| 新旧 CIK 但无充分 succession 证据 | `NEEDS_IDENTITY_REVIEW` |

## 4. 身份事件分类与处理决策

| 情况 | `company_id` | `display_name` | `primary_cik` | CIK role | 财务数据处理 |
|---|---|---|---|---|---|
| 同 CIK，简单更名 | 不变 | 更新为当前名称 | 不变 | 保持 `PRIMARY` | 同一 filer 历史，但仍按事实选择规则计算 |
| 同 CIK，仅 ticker 变化 | 不变 | 通常不变 | 不变 | 保持 `PRIMARY` | 财务计算不受 ticker 影响 |
| 同 CIK，但重大重组或业务实质替换 | 进入身份审核 | 更新为当前名称 | 不变 | 可能仍是 `PRIMARY` | 中断可比性，不能因 CIK 相同自动做同比 |
| 新 CIK，确认 successor/predecessor | 通常延续逻辑 `company_id` | 更新为当前名称 | 改为新 CIK | 新 CIK=`SUCCESSOR`，旧 CIK=`PREDECESSOR` | 当前指标只用新 CIK，跨 CIK YoY 默认禁止 |
| 新 CIK，实际为不同公司或业务 | 创建新 `company_id` | 各自名称 | 各自 CIK | 各自 `PRIMARY` | 完全分开，可另存关系但不合并指标 |
| 新 CIK，关系不明确 | 暂不自动分配或合并 | 保留候选名称 | 不自动切换 | 不自动创建 predecessor/successor | `NEEDS_IDENTITY_REVIEW` |

### 4.1 为什么 CIK 相同仍需连续性判断

法律主体变化和 CIK 变化并不是一一对应的。Rule 12g-3 succession 中，successor 可能使用新的 CIK，也可能承接 predecessor 的申报属性并继续使用原有 CIK。

```text
CIK 不变 ≠ 一定经济连续
CIK 改变 ≠ 一定完全不连续
```

SEC 要求 successor 就 succession 交易提交 8-K，并可能生成新的文件编号。[SEC Rule 12g-3 解释](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/exchange-act-rules)。实际 SEC 文件中既有 successor 承接旧 CIK 的案例，也有 predecessor 保留旧 CIK、successor 使用新 CIK 的案例：[承接旧 CIK 的 8-K](https://www.sec.gov/Archives/edgar/data/809248/000121390019007896/f8k12b043019_carrolsrestaur.htm)，[successor 使用不同 CIK 的 8-K](https://www.sec.gov/Archives/edgar/data/1981792/000110465923090466/tm2323105d1_8k12b.htm)。

## 5. 简单更名的处理规则

适用条件：

```text
CIK 不变
+ 只有 current/former name 变化
+ 无重大主体或报告口径变化证据
```

处理动作：

- 保留同一个 `company_id`；
- 保留同一个 `primary_cik`；
- 更新 `display_name`；
- 仅当 SEC 或交易所元数据表明 ticker 确实变化时才更新 ticker；
- 将 SEC `formerNames` 作为名称变化证据；如果需要离线审计，再写入本地名称历史；
- 保留该 CIK 的全部原始 Company Facts；
- 指标计算仍按 accession、form、期间、duration、unit、consolidation scope 和概念候选规则筛选。

这里没有“旧公司财务数据”和“新公司财务数据”的天然分界，它们属于同一个 filer 的历史。但同一 CIK 并不免除重大重组、stub period、会计口径变化等可比性检查。

## 6. 新 CIK 与 `company_id`、名称、role 的分配

### 6.1 可以延续同一 `company_id` 的条件

只有同时满足以下条件，才可以考虑让新旧 CIK 共享一个逻辑 `company_id`：

- 有明确 SEC succession 文件或等价权威证据；
- 新旧 CIK 的角色和生效日期可以确定；
- 项目确认它们属于同一条逻辑业务或申报继任链；
- 关系经过人工审核并留下 evidence accession；
- 共享 `company_id` 不会被解释为允许跨 CIK 合并财务指标。

当前 Paramount 配置采用这种模式：

```text
company_id = paramount_skydance_paramount_global
primary_cik = 2041610
roles = successor:2041610;predecessor:813828
entity_continuity_status = successor_predecessor
```

同一 `company_id` 在这里表示“经过确认的继任链”，而不是“两个 CIK 的收入和净利润属于同一条可直接比较的序列”。

### 6.2 必须创建新 `company_id` 的情况

以下情况默认创建新的 `company_id`：

- 被收购公司与收购方；
- 分拆后独立上市的新公司；
- 反向并购后业务实质被替换；
- SPAC 壳主体和交易后运营企业不满足逻辑连续性条件；
- 旧主体继续独立存在和申报；
- 只有名称或 ticker 相似，没有充分 succession 证据。

公司之间可以另存 `ACQUIRED_BY`、`SPUN_OFF_FROM`、`MERGED_INTO` 等关系，但不得错误地使用 `PREDECESSOR/SUCCESSOR` 把财务数据拼成一条时间序列。

### 6.3 Role 的约束

Role 属于 `company_id` 与 CIK 的关系，不属于公司名称。

- `PRIMARY`：普通当前 filer；
- `SUCCESSOR`：经过审核的继任链中新 filer；
- `PREDECESSOR`：经过审核的继任链中旧 filer；
- `RELATED`：有关联但不构成财务继任；不得成为 `calculation_cik`。

本文使用大写 role 表示规范语义；当前 CSV 使用小写序列化值 `primary/successor/predecessor`。Phase 1 可以保留现有小写格式，但必须通过统一映射进行枚举校验，不能同时存在两套含义。

只有 `REVIEWED_SUCCESSION` 状态才能创建 `SUCCESSOR/PREDECESSOR` 关系。旧 CIK 不是在所有 CIK 变化场景下都会变成 predecessor。

## 7. 标准财务指标计算合同

### 7.1 唯一计算 CIK

一个 `company_id` 在一个计算时点必须只有一个 `calculation_cik`：

```text
calculation_cik = primary_cik
```

同时必须满足：

- `primary_cik` 出现在一个 active `PRIMARY` 或 `SUCCESSOR` role 中；
- 不存在第二个 active calculation role；
- 目标 10-K、Company Facts 和标准财务指标都来自该 CIK；
- 配置冲突时立即 Fail Fast，不允许按排序或文件出现顺序猜测。

### 7.2 当前指标和比较期

固定规则：

```text
当前标准财务指标：只使用 calculation_cik
比较期：只使用 calculation_cik 正式提交或重新列报的事实
旧 CIK Company Facts：默认不进入当前标准指标计算
跨 CIK YoY：默认禁止
```

如果 successor 的当前 CIK 在正式 filing 中重新列报了可比历史期间，可以使用，但必须同时满足：

- 来源仍为当前 `calculation_cik`；
- accession、form 和报告期间明确；
- 当前期和比较期使用兼容的概念、unit 和 consolidation scope；
- duration 满足年度指标要求；
- 不属于 `successor_predecessor`、`stub_period` 或 `major_reorg` 等不可比状态。

如果只有 predecessor CIK 能提供 prior-year fact，则默认不跨接。

### 7.3 状态语义

- `NOT_AVAILABLE_SEC`：当前计算 CIK 没有提供满足选择条件的事实；
- `NOT_MEANINGFUL`：事实存在，但因为主体连续性、期间长度、口径或跨 CIK 问题不应计算；
- `NEEDS_REVIEW`：有候选事实或身份关系，但证据不足以自动采用；
- `OK`：身份、期间、概念、来源和可比性检查均通过。

禁止为了填充指标而从 predecessor CIK 强行补数。

## 8. 旧 CIK 数据的留存边界

旧 CIK 数据默认保留，用于：

- 原始 SEC 证据和审计追溯；
- succession 关系确认；
- predecessor 历史展示；
- 8-K、Form 15、重组文件和名称历史研究；
- 必要时的人工比较或重述核验。

但默认不得用于：

- 当前 CIK 的标准财务指标；
- 自动跨 CIK YoY；
- 将两个法律主体的收入、利润、现金流或资产直接相加；
- 仅凭相同 concept 名称拼接历史曲线。

推荐输出边界：

- `metrics_matrix.csv`：标准财务指标只使用 `calculation_cik`；非财务文本或事件行必须明确 source CIK；
- `events.csv`：逐事件保留来源 CIK、role 和 accession；
- 可选 `predecessor_history.csv`：保存旧 CIK 历史，仅供参考，不进入当前计算；
- 原始 filing 和 Company Facts：按 CIK、accession 保留，不物理删除。

## 9. 8-K 跨 CIK 规则

### 9.1 检索范围与聚合范围分离

```text
检索层：允许在明确的 transition window 内读取完整 role chain
事件层：每条事件保留自己的 source CIK、role 和 accession
聚合层：由 metric_id 决定是否允许跨 CIK
```

### 9.2 建议的指标范围

| 指标 | 默认 scope | 跨 CIK 规则 |
|---|---|---|
| E01 M&A announcements | `TRANSITION_CHAIN` | 可以跨 CIK，但必须按交易去重 |
| C01/E03 管理层变化 | `TRANSITION_CHAIN` | 可以跨 CIK 观察交接，但保留每条事件的 source CIK |
| E02 Bankruptcy filings | `FILING_ENTITY` | 不跨 CIK 聚合，归属于提交 Item 1.03 的 filer |
| E04 Financial restatements | `FILING_ENTITY` | 不跨 CIK 聚合，归属于提交 Item 4.02 的 filer |
| E05 Material agreements | `FILING_ENTITY` | 默认不跨 CIK；只有证据确认同一交易时才去重归并 |
| Auditor change | `FILING_ENTITY` | 分 predecessor/successor 归属，不以逻辑公司名称直接合并 |

### 9.3 事件记录最低字段

```text
company_id
source_cik
entity_role
accession
filing_date
item_code
event_scope
event_key nullable
source_url
confidence
```

`event_key` 用于同一交易被 predecessor 和 successor 重复披露时去重。没有可靠 `event_key` 时，必须保留为不同来源事件，不能仅凭 Item code 相同去重。

## 10. 字段权威性与优先级

| 问题 | 当前或目标权威来源 |
|---|---|
| 逻辑分析公司是谁 | `company_id` |
| 当前标准财务计算使用哪个 CIK | `primary_cik`，并校验 active role |
| 需要检索哪些关联 CIK | `roles`；未来由 `company_cik_role` 驱动 |
| `related_ciks` | 只作派生摘要，不作为抓取或计算依据 |
| 当前展示名称 | `display_name` |
| SEC 名称历史 | `submissions.current name/formerNames` |
| 证券交易标识 | ticker/exchange 关联，只作可变属性 |
| filing 身份 | CIK + accession |
| 是否允许同比 | `entity_continuity_status` + 同 CIK + 期间与事实检查 |

## 11. 当前项目行为

### 11.1 已实现

- [company_registry.csv](config/company_registry.csv) 一行代表一个逻辑公司；
- `roles` 可以展开一个逻辑公司下的多个 CIK；
- filing inventory 会遍历所有 role CIK；
- [target_10k_for_company](scripts/sec_pipeline.py#L1985) 优先选择 `PRIMARY/SUCCESSOR`；
- [prior_10k_for_company](scripts/sec_pipeline.py#L2015) 要求 prior filing 与目标 CIK 相同；
- [entity_continuity_yoy_result](scripts/sec_pipeline.py#L3323) 会阻止 non-continuous、stub、major reorg 和跨 CIK YoY；
- 标准 Company Facts 指标围绕选中的 target CIK 计算；
- 原始事件仍保留 accession 和 CIK。

### 11.2 当前缺口

- `primary_cik` 尚未被强制验证为最终选中的 target CIK；
- `PRIMARY` 和 `SUCCESSOR` 当前排序优先级相同，配置冲突时可能依赖排序结果；
- [stage_companyfacts_inventory](scripts/sec_pipeline.py#L1831) 默认下载所有 role CIK 的 Company Facts；
- loader 检查字段存在，但没有完整验证非空、唯一性、role 枚举和 role/primary 一致性；
- `company_id` 尚未贯穿所有运行时关联，部分逻辑仍按 `display_name` 查找；
- [events.csv](outputs/events.csv) 没有 `company_id`、`entity_role` 和 `event_scope`；
- 8-K 聚合仍按 `display_name` 合并所有 role 事件；
- 聚合指标可能使用 target CIK 作为行级 CIK，但 accession 同时包含 predecessor 和 successor；
- 当前没有本地 `company_name_history`；
- 当前 `roles` 没有有效期、evidence accession 和审核状态。

## 12. 目标实现路径

### 12.1 Phase 1：最小边界修正

不重写 pipeline，只修身份与计算边界：

1. 新增唯一的 `calculation_cik` 解析与 Fail Fast 校验；
2. 标准 Company Facts 默认只下载 `calculation_cik`；
3. predecessor Company Facts 改为明确需要时按需下载；
4. 所有内部关联逐步从 `display_name` 改为 `company_id`；
5. 事件记录增加 `company_id`、`source_cik`、`entity_role` 和 `event_scope`；
6. 8-K 是否跨 CIK 聚合由 metric scope 决定；
7. 保留原始数据和旧输出的审计关联，不物理删除历史。

### 12.2 Phase 2：规范化身份历史

与后端设计中的 [company_cik_role](SEC_metrics_Raw_Data_后端交接简版_v1.0.md#L168) 对齐，避免再定义另一套平行身份模型。

建议对象：

```text
company
company_name_history
company_cik_role
identity_event
```

`company_cik_role` 建议字段：

```text
company_id
cik
role
is_current
valid_from
valid_to
evidence_accession
evidence_form
evidence_item
review_status
reviewed_at_utc
```

唯一约束至少包括：

```text
(company_id, cik, role, valid_from)
一个 company_id 只能有一个 is_current=true 的 calculation role
```

## 13. 身份变化检测与审核流程

不需要另一条完整指标 pipeline，只需要轻量身份事件检查：

```text
定期读取 SEC submissions 元数据
→ 比较 current name、formerNames、ticker、exchange 和 filing 变化
→ ticker/name 变化只生成关联信号
→ 检查 8-K、Form 15 和 succession 相关 filing
→ 生成 identity event candidate
→ 人工确认关系和证据
→ 更新 registry 或 company_cik_role
→ 只重跑受影响 company_id
```

建议审核状态：

```text
AUTO_CONFIRMED_RENAME
NEEDS_IDENTITY_REVIEW
REVIEWED_SUCCESSION
REVIEWED_SEPARATE_ENTITY
REJECTED
```

所有审核时间使用 UTC，所有身份变更必须保留来源 accession 和审核结论。

## 14. Fail Fast 规则

注册表或未来关系表必须验证：

- `company_id` 非空且唯一；
- `display_name` 非空；
- CIK 为合法数字并采用统一规范化格式；
- role 只能属于允许枚举；
- `primary_cik` 必须出现在一个 active `PRIMARY/SUCCESSOR` role 中；
- 一个 `company_id` 只能有一个 active calculation CIK；
- `RELATED/PREDECESSOR` 不得成为默认 `calculation_cik`；
- `entity_continuity_status` 必须属于允许枚举；
- succession role 必须有 evidence accession 和审核状态；
- `valid_from` 和 `valid_to` 均非空时必须满足 `valid_from <= valid_to`；
- 同一个 active CIK 不得无审核地绑定到两个不同 `company_id`；
- `related_ciks` 如保留，只能从 role 数据推导，不得成为第二套权威来源。

任何冲突都必须在抓取和指标计算前报错，不能用默认值或名称匹配继续运行。

## 15. 验收案例

### Case 1：同 CIK 简单更名

- `company_id` 不变；
- `primary_cik` 不变；
- `display_name` 更新；
- ticker 只有实际变化时才更新；
- 历史 facts 保留；
- 不产生新的 company 或跨 CIK 关系。

### Case 2：同 CIK 仅 ticker 变化

- 身份和财务指标不变化；
- ticker 仅作为新关联值记录；
- 不触发历史事实重算或重新归属。

### Case 3：同 CIK 重大重组

- 不因为 CIK 相同自动允许同比；
- `entity_continuity_status` 更新；
- 受影响期间指标输出 `NOT_MEANINGFUL` 或进入审核。

### Case 4：新 CIK，确认 successor

- 逻辑 `company_id` 可以延续；
- `primary_cik` 切换到新 CIK；
- 新旧 role 分别为 `SUCCESSOR/PREDECESSOR`；
- 标准指标只使用新 CIK；
- 旧 CIK facts 只保留或按需使用；
- 跨 CIK YoY 为 `NOT_MEANINGFUL`。

### Case 5：新 CIK，独立公司或 spin-off

- 创建新的 `company_id`；
- 两家公司各有自己的 `PRIMARY`；
- 可记录业务关系，但财务数据完全分开。

### Case 6：只有 former name 或 ticker 相似

- 不自动合并；
- 输出 `NEEDS_IDENTITY_REVIEW`；
- 在证据确认前不修改 `company_id`、`primary_cik` 或 role。

### Case 7：当前 CIK 重新列报比较期

- 比较事实必须来自当前 CIK；
- accession、期间、unit、scope 和 duration 检查通过后才能使用；
- 不从 predecessor CIK 补数。

### Case 8：8-K 多 CIK 事件

- 每条事件保留自己的 source CIK、role 和 accession；
- M&A/领导层交接可以按规则跨 CIK 观察；
- bankruptcy/restatement 不跨 CIK 聚合；
- 同一交易只有存在可靠 `event_key` 时才去重。

### Case 9：配置冲突

- `primary_cik` 不在 active role 中、出现两个 calculation CIK 或 role 非法时，pipeline 在抓取前 Fail Fast；
- 不允许通过排序、名称或 ticker 猜测当前主体。

## 16. 最终不变量

```text
SEC filer 身份
→ 由 CIK 判断

逻辑公司或继任链
→ 由 company_id + role + 有效期 + succession 证据判断

filing 身份
→ 由 CIK + accession 判断

财务数据是否可比
→ 由 calculation_cik + accession + 期间 + 会计口径
  + consolidation scope + entity_continuity_status 判断

ticker 和公司名称
→ 只作为可变属性与身份发现信号
```

最精炼的执行原则：

- 同 CIK 简单更名：延续同一公司历史，但仍执行事实和可比性检查。
- 新 CIK 且确认继任：可以共享逻辑 `company_id`，但标准财务指标默认只使用新 CIK。
- 新 CIK 且不是同一逻辑公司：创建新 `company_id`，财务数据完全分开。
- 跨 CIK 只服务于身份、审计和经明确授权的事件范围，不自动服务于财务同比。

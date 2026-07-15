# SEC_metrics 数据库边界与实施决策

**项目负责人版｜v1.0｜2026-07-15**

> 本文供项目负责人、产品和架构决策使用。它解释为什么当前只让后端建设 Raw Data 层、哪些事情以后再做，以及 FSD 落地后数据库边界是否变化。

---

## 1. 最终决策

当前后端人员只需要建设 **SEC Raw Data 持久化层**，不要求他理解：

- 财务指标定义；
- 行业适用性；
- XBRL concept 选择；
- parser 和 Python 类；
- Golden、Validation、Mutation；
- ComputationGraph；
- 四维业务状态；
- FSD 的完整架构。

当前交付给后端的内容只有：

1. 实际 raw data；
2. raw data 的最小字段说明；
3. 六张表的逻辑边界；
4. 去重、幂等、不可变和查询要求；
5. 一组可执行验收样例。

**当前不要求后端建设指标结果层。** 指标结果、候选、lineage、Dataset Version 等，等生产侧的数据合同稳定后，再以一个独立的 `DatasetPublishBundle v1` 接入。

这样可以同时满足两件事：

- 后端现在能立即开工，而且不需要学习 SEC_metrics 的内部架构；
- FSD 未来落地时，Raw Data 层不需要推倒重建，只需要增加结果层。

---

## 2. 责任边界

### 2.1 后端拥有并实现的事情

当前阶段：

1. 原始文件的持久化与可重取；
2. 按 SHA-256 去重；
3. 每次来源请求的审计记录；
4. 公司、CIK、filing、accession 的基础关系；
5. 必填字段、外键、枚举、唯一键等结构校验；
6. 幂等导入和 append-only 约束；
7. 按 hash、CIK、accession、URL、时间查询 raw data。

未来结果层接入后，后端再增加：

1. 结果版本持久化；
2. 原子发布；
3. current version 指针；
4. 固定版本只读查询；
5. 公开视图与审核视图的权限隔离。

### 2.2 生产侧拥有并实现的事情

Python/数据生产侧负责：

- SEC 文件发现和下载策略；
- JSON、SGML、HTML、XBRL、iXBRL 的解析；
- taxonomy 和 concept 解释；
- 指标计算和候选选择；
- applicability、observation、quality、publication 状态判定；
- 业务不变量；
- Golden、Validation、Mutation；
- Coverage Receipt；
- AI proposal；
- 最终写给后端的数据包生成。

### 2.3 后端不得承担的事情

数据库或后端服务不得判断：

- Revenue 数值是否合理；
- 某个 concept 是否可以作为 Revenue；
- 某个比率是否具有经济意义；
- 某个 approximation 是否可以发布；
- 某个 filing 是否覆盖了完整业务窗口；
- 某个 AI proposal 是否正确。

后端只判断：

```text
Schema 是否合法
引用是否存在
枚举是否在允许集合中
唯一键是否冲突
同一 ID 的内容是否一致
写入是否满足不可变和原子规则
```

这条边界必须长期保持，否则业务耦合会从数据库层重新进入系统。

---

## 3. 对“数据库不需要关心我们如何提供数据”的精确定义

这句话应改为：

> 数据库不关心数据由哪个 parser、Python 模块或 AI 产生；数据库只关心约定的数据对象和持久化语义。

因此需要区分两层：

### 3.1 Raw Data 合同

Raw Data 合同现在即可冻结，未来 FSD 落地后不应变化：

```text
RawAsset = 一组不可变的 exact bytes
SourceObservation = 一次请求或来源观察
Filing = 一个 accession
Company/CIK Role = 逻辑公司与 SEC 实体关系
PipelineRun = 一次采集运行
```

后续更换 parser、增加 AI、拆分 Python 模块，均不影响这些对象。

### 3.2 指标结果合同

指标结果合同不是当前 raw data 的一部分。

FSD 会改变或新增：

- 结果粒度；
- 四维状态；
- scope；
- definition version；
- result role；
- lineage；
- Dataset Version；
- 公开与审核权限。

因此，**不要把当前 `metrics_matrix.csv` 直接固化为最终数据库结构**。当前阶段保留旧 CSV 文件即可，结果层等合同稳定后另行接入。

结论是：

> Raw 层现在建好后不需要因 FSD 重构；未来只做加法，新增结果层，不修改 Raw 层语义。

---

## 4. 为什么不采用上一版复杂建库方案

上一版方案试图一次性把以下对象全部交给后端：

```text
canonical_observation
metric_candidate
computation_graph
lineage_edge
coverage_receipt
validation_result
catalog_release
taxonomy registry
dataset_version
public/review views
```

这些对象长期可能需要，但现在全部建设有三个问题：

1. 后端人员必须先理解大量 FSD 和财务语义；
2. 生产侧合同尚未全部原生输出，后端只能根据文档猜测；
3. 当前真正的前置需求只是持久化 raw data，提前建设会产生空表和无效抽象。

本次方案采用渐进原则：

```text
现在：Raw Data 层
以后：Canonical/Result 层
最后：AI proposal 和审核数据
```

只要 Raw Data 被正确、不可变地保存，后续任何新 parser 和新合同都可以离线重放，不会丢失信息。

---

## 5. 当前后端只需要建设的六张表

| 表 | 一行代表什么 | 主要作用 |
|---|---|---|
| `pipeline_run` | 一次 raw 数据采集或回灌运行 | 追踪导入批次和运行状态 |
| `company` | 一个逻辑分析公司 | 稳定 `company_id` 和展示信息 |
| `company_cik_role` | 一个公司与一个 CIK 在一段时间内的角色 | 支持 primary、successor、predecessor |
| `filing` | 一个 SEC accession | 保存 form、filed/report date 和 primary document |
| `raw_asset` | 一组 exact bytes | 内容地址、SHA-256、长度和存储 URI |
| `source_observation` | 一次 URL 请求/读取观察 | 保存 URL、时间、HTTP 结果、headers、错误和 raw_asset 引用 |

这六张表只表达来源事实，不表达财务业务结论。

### 5.1 物理存储建议

```text
Raw bytes：对象存储或受控共享文件系统
元数据：单实例关系数据库
```

当前约 218 MB raw evidence、859 条请求观察；即使外推到约 1000 家公司，也没有必要因此引入分布式数仓、图数据库或微服务体系。

数据库技术由后端选择。PostgreSQL、MySQL 或等价关系库均可；FSD 不要求具体实现。

---

## 6. 最重要的字段归属

### 6.1 RawAsset

只表示内容本身：

```text
raw_asset_id = sha256(exact_bytes)
content_length
storage_uri
first_seen_at_utc
可选的 media_type_hint
```

不得把以下字段放入 RawAsset 身份：

```text
URL
抓取时间
HTTP status
response headers
retry attempt
accession
document_name
```

### 6.2 SourceObservation

表示一次来源观察：

```text
observation_key
run_id
method
requested_url
observed_at_utc
http_status
response_headers
content_type
purpose
retry_attempt
error
raw_asset_id（无 body 时可以为空）
accession（可为空）
document_name（可为空）
```

同一 bytes 来自两个 URL：

```text
1 条 raw_asset
2 条 source_observation
```

同一 URL 在两个时间返回不同 bytes：

```text
2 条 raw_asset
2 条 source_observation
```

这一字段归属需要作为 FSD 的 1.1.1 勘误同步回主文档。

---

## 7. 能在后端解决的事情，应当留在后端

为了减少生产侧重复代码，以下能力由后端实现更合适：

| 能力 | 后端行为 |
|---|---|
| Hash 验证 | 收到文件后计算 SHA-256，并与 manifest 比较 |
| 内容去重 | 相同 hash 只保存一份 bytes |
| Storage URI | 由后端分配或规范化，禁止保存开发者本机绝对路径 |
| 幂等导入 | 相同批次重复提交不得产生重复记录 |
| 冲突检测 | 同一业务键不同内容必须拒绝并告警，不得覆盖 |
| 不可变性 | raw_asset/source_observation 原则上 insert-only |
| 引用完整性 | filing、run、raw_asset 外键由数据库保证 |
| 查询和分页 | 按 CIK、accession、hash、URL、时间提供基础查询 |
| 备份和生命周期 | 对象存储和数据库的备份、归档、恢复由后端负责 |

以下能力即使后端技术上能做，也不得放入后端：

```text
解析 XBRL
选择 concept
计算指标
判断状态
修正数据
发布业务结论
```

---

## 8. 当前需要交给后端的 Raw Data 包

### 8.1 全量包

建议提供当前仓库的：

```text
evidence/
config/company_registry.csv
outputs/filing_inventory.csv（如存在）
```

当前仓库 raw evidence 约为：

```text
218 MB
859 条 requests_log 观察
submissions、companyfacts、accession materials、headers sidecar
```

### 8.2 联调最小样本

后端首次联调不需要先导入 218 MB。先提供以下代表样本：

1. 一份 submissions JSON + `.headers.json`；
2. 一份 Company Facts JSON + `.headers.json`；
3. 一个完整 10-K accession 目录：`index.json`、主 HTML、XBRL instance、FilingSummary；
4. 一个 8-K：`.hdr.sgml` + 主 HTML；
5. 一条 HTTP 403/失败但有 body 的记录；
6. 一条 transport failure、无 body 的记录；
7. `requests_log.csv` 的完整表头和若干成功/重试样例；
8. `company_registry.csv` 中连续实体和 successor/predecessor 各一例。

### 8.3 必须附带的 manifest

交付包需要有一张 manifest，最低字段：

```text
observation_key
run_id
method
requested_url
observed_at_utc
http_status
purpose
retry_attempt
error
relative_file_path
headers_relative_path
content_length
sha256
accession（可空）
document_name（可空）
user_agent（可空）
company_id（可空）
cik（可空）
```

`observation_key` 必须在一个 manifest 中唯一，用于重复导入去重；它可以由交付工具根据 `run_id + method + URL + observed_at + retry_attempt` 生成。后端不应通过目录名反向猜测这些字段。

现有 `.headers.json` 和 `requests_log.csv` 是回灌 SourceObservation 的输入材料。导入完成后，无需把它们再次逐个当作 SEC RawAsset；可以整体归档原始回灌包。

---

## 9. 后端当前不需要建设的内容

本阶段不要求：

- 将 Company Facts 中所有 fact 拆成数据库行；
- 将 iXBRL 中所有 fact 拆成数据库行；
- 建 `canonical_observation`；
- 建 metric candidate 和 rejection；
- 建 ComputationGraph；
- 建业务 lineage；
- 建四维状态；
- 建 Catalog Release；
- 建 Dataset Version；
- 导入现有 230 条旧指标结果；
- 提供指标业务 API。

这些工作在生产侧能稳定输出新的结果数据包后再开始。

现有 `metrics_matrix.csv`、`metric_evidence.csv` 继续作为 Legacy 文件，不作为本阶段数据库权威输入。

---

## 10. FSD 落地后是否需要改 Raw 数据库

不需要改变本阶段六张表的核心语义。

FSD 落地后：

```text
RawAsset、SourceObservation、Company、CIK Role、Filing、PipelineRun
继续使用
```

随后新增：

```text
Canonical Observation 层
Dataset/Metric Result 层
Review/Candidate 层
```

因此数据库未来可能**增加表**，但不应重新解释或重建现有 Raw 表。

这比“一开始就建设最终十四张表”风险更低，也比“把所有内容存一个 JSON/BLOB”更有结构和审计性。

---

## 11. 当前验收门

Raw 层满足以下条件，即可认为本阶段完成：

1. 同一文件重复导入只产生一个 RawAsset；
2. 同一 RawAsset 可以被多个 SourceObservation 引用；
3. HTTP 失败但有 body 时，body 可以作为 RawAsset 保存；
4. transport failure 无 body 时允许 `raw_asset_id = null`；
5. 本机绝对路径没有进入权威 `storage_uri`；
6. 相同导入批次重复执行不产生重复数据；
7. RawAsset 和 SourceObservation 不允许被普通应用账号更新或删除；
8. 可以按 hash、URL、CIK、accession、时间定位 raw 文件；
9. 数据库保存的 content length 和 SHA-256 与实际对象一致；
10. 后端实现中不存在任何财务指标或 XBRL 业务判断。

---

## 12. 项目实施顺序

### Phase R0：合同冻结

- 冻结本方案和后端简版交接文档；
- 确认对象存储位置；
- 确认六张表及字段归属；
- 生成 manifest。

### Phase R1：小样本联调

- 导入代表样本；
- 验证去重、失败请求、重复导入和查询；
- 调整不影响语义的内部实现。

### Phase R2：全量 Raw 回灌

- 回灌当前 218 MB raw evidence；
- 对账 requests_log 行数、hash 和缺失对象；
- 生成回灌报告。

### Phase R3：生产侧接入

- Python 采集侧输出同一 manifest/ingest contract；
- 新数据直接写入 Raw 层；
- 本地 evidence 目录降级为缓存或开发 fixture。

### Phase D：未来结果层

- 等 FSD 的 DatasetPublishBundle 定稿；
- 后端只根据独立结果合同增加表和 API；
- 不要求后端阅读 parser 或指标代码。

---

## 13. 最终原则

本项目应当把数据库边界控制在以下一句话内：

> 后端负责可靠地保存、约束、版本化和查询我们明确交给他的对象；生产侧负责解释 SEC 数据并决定财务事实是什么。

当前只交 Raw 对象，是有意控制复杂度，而不是牺牲未来架构。

# SEC_metrics Databricks Raw 生产闭环操作手册

**版本：v1.0｜日期：2026-07-16（UTC）**

> 本手册从六张 Raw 表和对象存储已经通过验收开始，指导团队完成历史回灌、生产采集接入、完全离线重放和基线冻结。到基线冻结为止，不建设 Canonical、Metric Result、Gold 结果表或前端 API。

---

## 0. 最终目标

执行完本手册后，系统必须满足：

```text
现有 raw evidence 已全量进入 Databricks
→ 新的 SEC 请求自动写入 Raw 层
→ 指定历史 run_id 后可以完全断网重算
→ 重算结果与当前十家公司基线一致
→ 形成 baseline_release_v1
```

唯一总验收：

> 删除运行节点上的本地 `evidence/` 缓存并禁止访问 SEC 网络后，Databricks 仍能从固定 RawAsset 集合重新生成同样的 metrics、evidence、Golden 和 Validation 结果。

---

## 1. 范围与禁止项

### 1.1 本手册包含

1. Databricks 运行参数与权限确认；
2. 当前结果的对照快照；
3. 现有约 217 MB raw evidence 的全量回灌；
4. 约 859 条历史请求 attempt 的 SourceObservation 回灌；
5. 现有 Python SEC 请求接入 Raw 层；
6. 完全离线重放；
7. 新旧输出比较；
8. `baseline_release_v1.json` 冻结。

上述数量来自 2026-07-16 工作区快照，正式执行时必须重新统计，不得硬编码。

### 1.2 本手册不包含

- 不重写指标算法；
- 不调整 Golden expected；
- 不把 `metrics_matrix.csv` 建成最终数据库表；
- 不建设 Canonical Observation 表；
- 不建设 Dataset Version、Metric Result 或 Gold 结果层；
- 不建设前端 API；
- 不引入 Lakebase、Kafka、Airflow 或 AI 主链路。

### 1.3 与现有 Databricks 沟通稿的关系

`Databricks生产化方案_产品与前端沟通版.html` 描述了更远期的结果发布和 API。当前操作以本手册为准，先完成 Raw 生产闭环；结果层必须等 Result Bundle v1 冻结后单独实施。

---

## 2. 执行前必须知道的当前事实

当前仓库仍然：

- 由 `SecHttpClient.fetch(...)` 请求 SEC 并直接写入本地 `evidence/`；
- 由 parser 从固定本地路径读取 Company Facts、submissions 和 accession materials；
- 没有 `databricks.yml`；
- 没有 Python wheel 打包配置；
- 没有 RawStore reader/writer；
- 没有 offline replay 入口。

因此需要先完成一次性的“工程接入”，然后操作员才能执行“回灌—联机运行—离线重放—冻结基线”。

---

## 3. Databricks 对象与集中参数

### 3.1 只使用以下对象

| Databricks 对象 | 用途 |
|---|---|
| Unity Catalog Volume：Raw | 保存不可变 exact bytes；沿用已验收的 managed 或 external 类型 |
| Unity Catalog Volume：Ops | 保存 staging、manifest、报告、replay 和 baseline artifact |
| 六张 Unity Catalog Delta 表 | 保存 Raw 元数据和基础关系 |
| Lakeflow Jobs | 编排回灌、联机运行和离线重放 |
| Job service principal | 生产运行身份 |
| SQL Warehouse 或 Job compute | 执行验收查询和任务 |

Raw exact bytes 必须使用受 Unity Catalog 治理的 Volume；表格元数据必须使用 Unity Catalog Delta 表。

### 3.2 集中参数

以下参数只允许在 Job parameters 或一个受版本控制的环境配置中定义。代码不得散落硬编码。

| 参数 | 示例 | 说明 |
|---|---|---|
| `environment` | `prod` | 环境名称 |
| `catalog` | `sec_metrics_prod` | Unity Catalog catalog |
| `raw_schema` | `raw` | 六张 Raw 表所在 schema |
| `raw_volume` | `raw_assets` | exact bytes Volume |
| `ops_volume` | `raw_ops` | staging、报告和 baseline Volume |
| `run_mode` | `ONLINE` | `ONLINE` 或 `OFFLINE_REPLAY` |
| `backfill_id` | `backfill_v1_20260716T120000Z` | 一次回灌的稳定 ID |
| `source_run_id` | 空或指定值 | 离线重放时必填 |
| `reference_id` | `legacy_10_company_v1` | 当前对照快照 ID |
| `code_commit` | Git SHA | 运行代码版本 |
| `force_full` | `false` | 是否强制执行完整运行 |

时间统一使用 UTC ISO-8601：

```text
2026-07-16T12:00:00Z
```

运行时代码使用：

```text
/Volumes/<catalog>/<schema>/<volume>/...
```

Databricks CLI 上传文件时使用：

```text
dbfs:/Volumes/<catalog>/<schema>/<volume>/...
```

### 3.3 推荐 Volume 目录

```text
/Volumes/<catalog>/<raw_schema>/<raw_volume>/
└── sha256/
    └── ab/
        └── <完整 SHA-256>

/Volumes/<catalog>/<raw_schema>/<ops_volume>/
├── staging/backfill/<backfill_id>/
├── manifests/backfill/
├── reports/backfill/
├── reference/<reference_id>/
├── replay/<replay_run_id>/
└── baseline/<baseline_id>/
```

RawAsset 存储 URI 规则：

```text
/Volumes/<catalog>/<raw_schema>/<raw_volume>/sha256/<hash前两位>/<完整hash>
```

同一 SHA-256 永远映射到同一路径。不得使用公司名、CIK、accession 或本机路径作为 RawAsset 身份。

---

## 4. 权限和运行身份

### 4.1 Job 身份

所有生产 Job 的 `Run as` 必须设置为专用 service principal，不得使用开发者个人账号。

建议角色：

| 身份 | 权限 |
|---|---|
| `sec_metrics_raw_job_sp` | 读取配置；写 Raw/Ops Volume；写六张表；运行 Job |
| `sec_metrics_raw_reader` | 只读六张表和 Raw Volume |
| `sec_metrics_operator` | 查看运行、触发运行，不得修改代码和 Raw 数据 |
| `sec_metrics_admin` | 管理 Job、权限、恢复和紧急处理 |

### 4.2 写入纪律

- `raw_asset` 和 `source_observation` 只允许 insert-only merge；
- 同一主键内容一致时跳过；
- 同一主键内容不一致时立即失败并生成冲突报告；
- 不允许 matched update；
- 不允许 delete；
- 回灌 Job 最大并发运行数设置为 `1`；
- 生产联机 Job 最大并发运行数设置为 `1`。

Databricks 的主键和外键属于信息性约束，不能代替应用侧的唯一性、冲突和悬空引用检查。

---

## 5. 一次性工程接入

本节由 Python/数据工程人员完成。完成后，日常操作员不再修改代码。

### 5.1 最小交付物

只增加一个 Python 包和以下五个入口：

| 入口 | 职责 |
|---|---|
| `prepare_reference` | 固定当前代码、配置、输入和输出快照 |
| `backfill_raw` | 导入历史 RawAsset、SourceObservation 和基础关系 |
| `run_online` | 联网运行，所有新请求写入 Raw 层 |
| `replay_offline` | 禁止联网，从指定 run 的 RawAsset 重算 |
| `freeze_baseline` | 验收通过后生成正式 baseline manifest |

入口名称可以调整，但职责不得合并成无法单独验收的大脚本。

所有参数：

- 必须使用关键字参数；
- 缺失时立即报错；
- 不允许用 `None` 继续运行；
- 不允许通过隐式环境状态猜测 catalog、schema、run 或模式。

### 5.2 RawStore 最小行为

生产代码需要一个明确的数据接口：

```text
begin_run(...)
put_raw_asset(bytes, expected_sha256)
record_source_observation(...)
finish_run(...)
read_raw_asset(raw_asset_id)
find_run_assets(run_id)
```

行为要求：

1. `put_raw_asset` 重新计算 SHA-256；
2. hash 不一致立即失败；
3. 相同 hash 已存在时验证长度和 URI 后复用；
4. `record_source_observation` 每个 request attempt 写一行；
5. transport failure 无 body 时允许 `raw_asset_id = null`；
6. HTTP 错误有 body 时仍保存 RawAsset；
7. Offline 模式只能调用读取接口。

### 5.3 两种运行模式

#### `ONLINE`

```text
创建 pipeline_run
→ 请求 SEC
→ 将 exact bytes 写入 Raw Volume
→ insert-only merge raw_asset
→ insert source_observation
→ parser 处理相同 bytes
→ 生成当前 Legacy 输出
```

#### `OFFLINE_REPLAY`

```text
验证 source_run_id
→ 禁止构造 SecHttpClient
→ 从 Raw 层读取固定 RawAsset
→ parser 处理相同 bytes
→ 生成当前 Legacy 输出
→ 与 reference/baseline 比较
```

Offline 模式中发现缺失 RawAsset 必须失败，不得自动切换到网络。

### 5.4 不要在这一步净化算法

为保证可比较性，本阶段保留当前：

- parser；
- 指标计算；
- repair 行为；
- Golden；
- Validation；
- CSV 字段；
- 排序规则。

报告阶段目前仍会应用 repair。先保证重放 parity，之后再将流程重构为：

```text
parse → resolve → validate → export
```

---

## 6. 建立三个 Databricks Job

### 6.1 Job A：`sec_metrics_raw_backfill_v1`

人工触发，仅用于历史回灌。

```text
preflight
→ validate_staging_package
→ import_company_and_roles
→ import_filings
→ import_raw_assets
→ import_source_observations
→ reconcile_backfill
```

Job parameters：

```text
catalog
raw_schema
raw_volume
ops_volume
backfill_id
code_commit
```

任何任务失败时，下游任务不得继续。使用相同 `backfill_id` 重跑必须幂等。

### 6.2 Job B：`sec_metrics_pipeline_online`

先人工触发完成验收，之后才允许设置正式调度。

```text
preflight
→ start_run
→ run_current_pipeline_online
→ reconcile_new_raw
→ run_golden
→ run_validation
→ finish_run
```

Job parameters：

```text
catalog
raw_schema
raw_volume
ops_volume
run_mode=ONLINE
code_commit
force_full
```

### 6.3 Job C：`sec_metrics_offline_replay`

人工触发，也应进入发布前回归。

```text
replay_preflight
→ resolve_fixed_raw_assets
→ run_current_pipeline_offline
→ compare_outputs
→ write_replay_report
```

Job parameters：

```text
catalog
raw_schema
raw_volume
ops_volume
run_mode=OFFLINE_REPLAY
source_run_id
reference_id
code_commit
```

三个 Job 都应：

- 使用同一 service principal；
- 默认单并发；
- 参数缺失立即失败；
- 记录 Git commit；
- 记录开始和结束 UTC 时间；
- 失败时保留已生成的诊断 artifact；
- 不在日志中输出凭据。

---

## 7. 操作一：生成当前对照快照

在修改当前采集读写方式前执行。

### 7.1 本地验证

在仓库根目录运行：

```bash
python3 -m unittest tests/test_sec_pipeline_validation.py
python3 tools/check_no_company_literals.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/12_validate_repair.py
```

任何一项失败都不得开始 Databricks 迁移。

### 7.2 对照快照内容

`prepare_reference` 至少记录：

```text
reference_id
created_at_utc
git_commit
company_registry SHA-256
metric_applicability SHA-256
sec_config 非敏感字段 SHA-256
目标 company / CIK / accession
evidence 文件数与总字节数
requests_log attempt 数
metrics_matrix SHA-256
metric_evidence SHA-256
golden_results SHA-256
repair_validation_results SHA-256
测试结果
```

并复制以下文件到：

```text
/Volumes/<catalog>/<raw_schema>/<ops_volume>/reference/<reference_id>/
```

文件：

```text
config/company_registry.csv
config/metric_applicability.yaml
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
outputs/golden_results.csv
outputs/repair_validation_results.csv
outputs/coverage_matrix.csv
REPORT_十公司财务指标.md
reference_manifest.json
```

此处是迁移对照快照，不是最终 `baseline_release_v1`。

---

## 8. 操作二：全量回灌

### 8.1 生成 backfill package

输入：

```text
evidence/submissions/
evidence/companyfacts/
evidence/accession_materials/
evidence/company_tickers/
evidence/requests_log.csv
config/company_registry.csv
```

生成：

```text
backfill_package/
├── payload/
├── raw_backfill_manifest_v1.jsonl
├── company.csv
├── company_cik_role.csv
├── filing.csv
└── package_manifest.json
```

每个 request attempt 必须有一条 manifest 记录。

Headers sidecar：

- 用于构造 `response_headers_json`；
- 不重复作为 SEC RawAsset；
- 原始 backfill package 整体保存在 Ops Volume，供审计。

### 8.2 上传 staging

在本地终端执行：

```bash
databricks fs cp \
  /absolute/path/to/backfill_package \
  dbfs:/Volumes/<catalog>/<raw_schema>/<ops_volume>/staging/backfill/<backfill_id> \
  --recursive
```

同一 `backfill_id` 已存在时不得使用 `--overwrite`。应先确认它是同一 package，或使用新的 `backfill_id`。

### 8.3 运行 Job A

在 Databricks：

```text
Jobs & Pipelines
→ sec_metrics_raw_backfill_v1
→ Run now with different parameters
→ 填入 catalog/raw_schema/raw_volume/ops_volume/backfill_id/code_commit
→ Run
```

### 8.4 Job A 必须执行的写入顺序

```text
验证 package manifest
→ 校验 manifest 内部 observation_key 唯一
→ 校验 manifest 内部 raw_asset_id 与 bytes 一致
→ 上传/复用 content-addressed bytes
→ insert-only merge company
→ insert-only merge company_cik_role
→ insert-only merge filing
→ insert-only merge raw_asset
→ insert-only merge source_observation
→ 执行全量对账
```

不要假设六张表可以自动跨表原子提交。每一步都必须幂等，并通过 `pipeline_run` 状态和对账报告识别部分完成。

### 8.5 回灌验收 SQL

将 `<catalog>.<raw_schema>` 替换成实际名称。

#### RawAsset 主键重复

```sql
SELECT
  raw_asset_id,
  COUNT(*) AS row_count
FROM <catalog>.<raw_schema>.raw_asset
GROUP BY raw_asset_id
HAVING COUNT(*) > 1;
```

预期：0 行。

#### SourceObservation 幂等键重复

```sql
SELECT
  observation_key,
  COUNT(*) AS row_count
FROM <catalog>.<raw_schema>.source_observation
GROUP BY observation_key
HAVING COUNT(*) > 1;
```

预期：0 行。

#### RawAsset 悬空引用

```sql
SELECT COUNT(*) AS orphan_reference_count
FROM <catalog>.<raw_schema>.source_observation AS observation
LEFT ANTI JOIN <catalog>.<raw_schema>.raw_asset AS asset
  ON observation.raw_asset_id = asset.raw_asset_id
WHERE observation.raw_asset_id IS NOT NULL;
```

预期：0。

#### 禁止本机路径

```sql
SELECT
  raw_asset_id,
  storage_uri
FROM <catalog>.<raw_schema>.raw_asset
WHERE storage_uri RLIKE '^(file:|/Users/|/home/|/tmp/)';
```

预期：0 行。

#### Run 状态

```sql
SELECT
  run_id,
  status,
  started_at_utc,
  finished_at_utc
FROM <catalog>.<raw_schema>.pipeline_run
WHERE run_id = '<backfill_id>';
```

预期：一行，状态为 `SUCCEEDED`。

### 8.6 回灌报告

必须生成：

```text
/Volumes/<catalog>/<raw_schema>/<ops_volume>/
  reports/backfill/<backfill_id>/
    raw_backfill_reconciliation_report.json
    raw_backfill_reconciliation_report.md
```

最低字段：

```text
manifest_attempt_count
source_observation_count
body_attempt_count
raw_asset_reference_count
unique_raw_asset_count
total_bytes
hash_mismatch_count
content_length_mismatch_count
duplicate_observation_key_count
orphan_reference_count
unmatched_company_count
unmatched_filing_count
idempotent_rerun_delta
```

退出条件：

```text
hash_mismatch_count = 0
content_length_mismatch_count = 0
duplicate_observation_key_count = 0
orphan_reference_count = 0
idempotent_rerun_delta = 0
```

未匹配 company 或 filing 可以非零，但必须附明细，不能猜测或丢弃。

---

## 9. 操作三：联机生产接入验收

### 9.1 首次运行

人工触发 Job B，设置：

```text
run_mode=ONLINE
force_full=true
```

首次验收运行必须覆盖当前 registry 中的全部十家公司，不能只跑一家公司后就宣告完成。

### 9.2 验收内容

运行完成后验证：

1. 每次 SEC request attempt 都产生一条 SourceObservation；
2. 同一 bytes 不产生第二条 RawAsset；
3. HTTP 错误有 body 时存在 RawAsset；
4. transport failure 无 body 时 SourceObservation 仍存在；
5. 新 run 的所有 RawAsset 均可从 Volume 读取；
6. 当前 `metrics_matrix.csv` 等 Legacy 输出仍能生成；
7. Golden 和 Validation 结果没有因存储接入变化而改变。

### 9.3 恢复本地缓存测试

在一个新的 Job run 工作目录中：

```text
不复制原 evidence/
→ 根据刚完成的 source_run_id 从 Raw 层恢复所需文件
→ 校验每个文件 SHA-256
→ 确认 parser 可以读取
```

本地 `evidence/` 从此只能是缓存或开发 fixture，不再是唯一证据源。

---

## 10. 操作四：完全离线重放

### 10.1 启动

人工触发 Job C：

```text
run_mode=OFFLINE_REPLAY
source_run_id=<已通过联机验收的 run_id>
reference_id=legacy_10_company_v1
```

### 10.2 Offline 硬门禁

代码必须在任何计算开始前验证：

```text
run_mode == OFFLINE_REPLAY
source_run_id 非空
source_run_id 状态为 SUCCEEDED 或已批准的 PARTIAL
固定 RawAsset 清单存在
所有 RawAsset bytes 可读且 hash 一致
SecHttpClient 未被实例化
```

建议同时使用工作区网络策略阻断 SEC 域名，作为第二层防护；但网络策略不能替代代码中的 Offline fail-fast。

### 10.3 运行行为

```text
从 source_run_id 解析固定 SourceObservation
→ 得到固定 RawAsset IDs
→ 将 exact bytes 放入 run-local 临时目录或直接交给 parser
→ 用 RawAsset 可用性检查替代联网的 M0 smoke test
→ 运行当前 M1-M7 等价流程
→ 运行 Golden
→ 运行 Validation
→ 生成标准化 diff
```

不得读取：

- 最新 filing；
- 其他 run 的较新 SourceObservation；
- 本地遗留缓存；
- SEC 网络；
- 未登记的人工修补文件。

### 10.4 输出比较

必须比较：

```text
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
outputs/golden_results.csv
outputs/repair_validation_results.csv
outputs/coverage_matrix.csv
```

比较前统一：

- UTF-8；
- 换行符；
- CSV 列顺序；
- 业务主键排序；
- Decimal 文本格式。

只允许忽略预先登记的环境字段：

| 文件 | 可忽略字段 |
|---|---|
| `metric_evidence.csv` | `local_path`，但必须另行验证对应 RawAsset |
| 人类报告 | `generated_at_utc` 等生成时间 |

由于当前 `metric_evidence.csv` 尚未包含 `raw_asset_id`，Replay Job 必须额外输出：

```text
legacy_path_raw_asset_mapping.csv
```

每一条被忽略的 `local_path` 都必须映射到固定 `raw_asset_id`，且 bytes hash 校验通过。无法映射时不得忽略该差异。

以下字段不得忽略：

```text
company
cik
metric_id
value
unit
status
source_class
formula
period
accession
concept_or_section
context_or_dimension
source_url
evidence_quote
extraction_method
parser_version
```

### 10.5 Replay 报告

生成：

```text
/Volumes/<catalog>/<raw_schema>/<ops_volume>/
  replay/<replay_run_id>/
    offline_replay_manifest.json
    offline_replay_diff.csv
    offline_replay_report.md
```

报告最低字段：

```text
replay_run_id
source_run_id
reference_id
code_commit
raw_asset_count
raw_asset_hash_mismatch_count
network_client_construction_count
network_request_count
missing_raw_asset_count
metrics_diff_count
evidence_diff_count
golden_diff_count
validation_diff_count
ignored_diff_count
final_status
```

通过标准：

```text
raw_asset_hash_mismatch_count = 0
network_client_construction_count = 0
network_request_count = 0
missing_raw_asset_count = 0
metrics_diff_count = 0
evidence_diff_count = 0
golden_diff_count = 0
validation_diff_count = 0
final_status = PASS
```

### 10.6 必做失败测试

在非生产副本中，从 replay manifest 删除一个必需 RawAsset 引用后运行：

预期：

```text
Job 立即失败
错误中明确列出缺失 raw_asset_id
network_request_count 仍为 0
不生成伪成功结果
```

---

## 11. 操作五：冻结 baseline_release_v1

只有 Offline Replay 全部通过后执行 `freeze_baseline`。

### 11.1 Baseline 内容

```text
baseline_id
created_at_utc
approved_by
git_commit
company_registry_sha256
metric_applicability_sha256
source_run_id
replay_run_id
company / CIK / accession 清单
raw_asset_id 清单及 SHA-256
metrics_matrix SHA-256
metric_evidence SHA-256
golden_results SHA-256
repair_validation_results SHA-256
coverage_matrix SHA-256
测试命令和结果
replay diff 汇总
批准的忽略字段
```

### 11.2 保存位置

```text
/Volumes/<catalog>/<raw_schema>/<ops_volume>/
  baseline/baseline_release_v1/
    baseline_release_v1.json
    raw_asset_manifest.jsonl
    outputs/
    validation/
    replay_report/
```

同时将不含大体量 Raw bytes 的：

```text
baseline_release_v1.json
```

纳入 Git 评审。

### 11.3 冻结后的规则

- 不得在运行时刷新 Golden expected；
- 任何 Expected 变化必须提交 baseline change；
- parser、resolve 或指标算法变更必须与该 baseline 双跑；
- Raw 表语义保持不变；
- 后端此时可以暂停领域建模；
- 下一阶段是生产侧 pipeline 净化，不是立即建设结果表。

---

## 12. 日常生产运行

完成基线冻结后，Job B 才能设置调度。

### 12.1 每次运行

```text
创建 pipeline_run
→ 执行 SEC 请求
→ 写 RawAsset/SourceObservation
→ 运行现有计算
→ Golden/Validation
→ 记录 SUCCEEDED/PARTIAL/FAILED
```

### 12.2 每次运行后的最低检查

```sql
SELECT
  run_id,
  status,
  started_at_utc,
  finished_at_utc,
  notes
FROM <catalog>.<raw_schema>.pipeline_run
ORDER BY started_at_utc DESC
LIMIT 20;
```

并检查：

- 本 run 的请求 attempt 数；
- 新增 RawAsset 数；
- 重试数；
- 无 body failure 数；
- hash mismatch 数；
- Golden/Validation 状态。

### 12.3 定期离线重放

至少在以下情况触发 Job C：

- parser 版本变化；
- Python 依赖版本变化；
- Databricks Runtime 升级；
- RawStore 代码变化；
- 指标算法变化；
- 发布前；
- 发生 SEC 格式漂移后。

---

## 13. 故障处理

### 13.1 Hash 不一致

处理：

```text
拒绝该 RawAsset
→ 保留 staging 文件
→ 写明 expected/actual hash
→ 标记 run FAILED
→ 检查传输或 manifest 生成
```

禁止覆盖已有 RawAsset。

### 13.2 相同 observation_key、内容不同

处理：

```text
停止写入
→ 生成 conflict report
→ 比较 run_id、URL、时间、retry_attempt 和 body
→ 修复 observation_key 生成规则或源 manifest
```

不得执行 UPDATE。

### 13.3 回灌部分完成

使用相同 `backfill_id` 重跑。由于每一步是 insert-only 和幂等：

- 已存在且内容一致的对象跳过；
- 缺失对象继续写入；
- 内容冲突立即失败。

不得先删除已完成数据再重跑。

### 13.4 Offline Replay 试图联网

处理：

```text
立即失败
→ 记录调用位置
→ 不接受“网络补抓后结果一致”
→ 将该调用改为 RawStore 读取
```

### 13.5 输出存在差异

按顺序分类：

1. 仅本机路径或生成时间；
2. 行顺序或 Decimal 格式；
3. parser/依赖版本变化；
4. 使用了错误 run 或最新 filing；
5. 缺失 RawAsset；
6. 真实业务值、状态或证据变化。

第 3—6 类不得通过修改 Golden expected 掩盖。

### 13.6 恢复与备份

- Delta Time Travel 用于短期排错，不作为长期备份；
- Volume 和 Delta 表必须纳入平台备份与恢复方案；
- 恢复演练后重新验证 RawAsset hash、表行数和引用；
- 不要依赖仍处于预览状态的跨表事务能力作为唯一恢复保证。

---

## 14. 最终 Go / No-Go 清单

### Gate R1：历史回灌

- [ ] 当前 evidence 全量进入 Volume；
- [ ] 全部 request attempts 进入 SourceObservation；
- [ ] hash mismatch 为 0；
- [ ] content length mismatch 为 0；
- [ ] duplicate observation_key 为 0；
- [ ] orphan reference 为 0；
- [ ] 相同 backfill 重跑差异为 0。

### Gate R2：生产接入

- [ ] 新 SEC 请求全部写入 Raw 层；
- [ ] 相同 bytes 正确去重；
- [ ] 失败请求保留；
- [ ] 本地缓存删除后可恢复；
- [ ] Legacy 输出、Golden、Validation 保持不变。

### Gate R3：离线重放

- [ ] 网络 client 构造次数为 0；
- [ ] 网络请求数为 0；
- [ ] 缺失 RawAsset 数为 0；
- [ ] metrics 差异为 0；
- [ ] evidence 差异为 0；
- [ ] Golden 差异为 0；
- [ ] Validation 差异为 0；
- [ ] 缺失 RawAsset 失败测试通过。

### Gate B0：基线冻结

- [ ] `baseline_release_v1.json` 已生成；
- [ ] RawAsset 清单已固定；
- [ ] Git commit 已固定；
- [ ] 输出 hash 已固定；
- [ ] 审批人已记录；
- [ ] Baseline manifest 已进入 Git 评审。

只有四个 Gate 全部通过，才可以开始 pipeline 净化。

---

## 15. Databricks 官方参考

- Unity Catalog Volumes：<https://docs.databricks.com/aws/en/volumes/volume-files>
- Databricks CLI 文件操作：<https://docs.databricks.com/aws/en/dev-tools/cli/reference/fs-commands>
- Lakeflow Jobs Python wheel task：<https://docs.databricks.com/aws/en/jobs/tasks/python-wheel>
- Job parameters：<https://docs.databricks.com/aws/en/jobs/job-parameters>
- Job service principal 与权限：<https://docs.databricks.com/aws/en/jobs/privileges>
- Delta insert-only deduplication：<https://docs.databricks.com/aws/en/delta/merge>
- Databricks 表约束：<https://docs.databricks.com/gcp/en/tables/constraints>
- Delta table history 与 Time Travel：<https://docs.databricks.com/gcp/en/tables/history>

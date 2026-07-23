# SEC、XBRL 与证据模型

> Status: stable concept document
> Dynamic run counts and verdicts are intentionally excluded.

## 1. 项目在解决什么

SEC_metrics 是配置驱动、SEC-only 的单财年批处理研究流程。它的成功标准不是“每个指标都有数字”，而是每个适用的公司 × 指标格都有可解释的 value 或明确 status，并能追溯到 SEC 原始材料、口径和证据。

```text
company × metric
→ value / status / formula / source / evidence / confidence
```

猜数填满矩阵是失败；明确写出未披露、未抽取、不适用、不可比或待复核是合法结果。

## 2. 三个数据平面

### Submissions

回答“公司提交了什么”，用于公司身份、财年底、target/prior 10-K、DEF 14A 与财年窗口 8-K inventory。

### Companyfacts

聚合标准 taxonomy、公司整体层面的 XBRL facts，适合 revenue、net income、assets、cash 等标准事实。它不覆盖全部 dimensional facts、公司扩展 concepts 或复杂文本表格。

### Accession materials

单份 filing 的原始目录与文档，包括 index、header、primary iXBRL/XML instance、FilingSummary 及其他附件。维度事实、扩展 concept、8-K item、DEI AuditorName、MD&A/DEF 14A 表格与文本证据需要进入这一层。

因此当前策略是：

```text
companyfacts first
→ accession-aware fallback
→ text/table extraction only when structured facts are insufficient
```

## 3. XBRL 最小词汇

- **concept**：事实的语义名称；可能来自标准 taxonomy，也可能是公司扩展。
- **context**：事实对应的期间、报告主体与维度。
- **dimension = axis + member**：例如资本比率的方法、法律实体或业务分部。
- **unit**：USD、pure 等。
- **scale/sign**：iXBRL 展示值到规范数值的换算信息。
- **accession**：单份 SEC filing 的唯一身份。

同一经济事实在不同公司可能使用不同 concept；可扩展性来自候选链、profile、capability probe 与维度语义，而不是公司名分支。

## 4. 两条主要证据链

### 数值指标

```text
SEC response bytes
→ normalized fact/inventory
→ component selection
→ metric formula
→ metrics_matrix row
→ metric_evidence row
```

可采信数值必须闭合 value、unit、period、accession、source URL、concept/section 与 extraction method。

### 事件与定性信号

```text
request-bound filing inventory
→ raw filing/header/primary document
→ exact event or text component set
→ metric/signal row
→ component or scan evidence
```

零事件只表示“在已定义并验证的扫描窗口内未命中”，不表示现实世界绝对不存在。

## 5. Portable locator

当前 locator 的联合身份是：

```text
source_url
repo_relative_path
content_sha256
accession
document_name
```

仓库内相对路径便于跨 clone 读取；URL、accession、document 与 hash 共同防止同名文件或错误 filing 错绑。历史绝对路径只能作为 relocation hint，不能作为权威地址。

## 6. Request ledger

所有生产请求统一经过 `SecHttpClient`：

- 只允许精确官方 SEC HTTPS origin；
- 不隐式跟随 redirect；
- 每个 client 进程内 pacing；
- 对配置的状态重试和退避；
- 每个已发 attempt 写 observation；
- 有 body 时保存 content-addressed immutable body/header；
- `requests_log_manifest.json` 绑定 CSV schema、row count 与整表 hash；
- Git baseline、下游 locator 与 sidecar 提供反向完整性约束。

## 7. Validation 的层次

```text
Golden
→ repair validation
→ stratified audit
→ validation run manifest
→ validation snapshot provenance
→ human/external acceptance
```

manifest 说明本轮刷新范围；snapshot provenance 说明当前 source/artifact bytes 仍与该 run 绑定；两者都不替代业务方法审查或外部接受。

## 8. C04 与 8-K 的稳定语义

- C04 审计师变更以 current/prior 10-K 的官方 DEI `AuditorName` 为主机制；8-K 不是该指标的权威重放路径。
- 8-K 事件由 submissions 定义完整财年窗口，再从 request-bound raw hdr/primary 重放 item，与 `events.csv` 和逐组件 evidence 做 exact-set 对齐。

## 9. 当前状态在哪里

稳定原理只在本文维护。任何当前数量、mismatch、测试数或 verdict 必须读取：

```text
outputs/validation_run_manifest.json
outputs/validation_snapshot_provenance.json
REPORT_十公司财务指标.md
outputs/repair_validation_results.csv
```

历史测量只存在于 `docs/history/`，并固定 commit/date。

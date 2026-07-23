# 历史设计入口：SEC 十公司单年指标 spike

> Status: historical compatibility redirect
> 本文件不再定义当前物理运行顺序、证据 schema 或验收终态。

## 当前应读什么

- 执行物理阶段 `00`–`12`：`README_RUN.md`
- 标准流程导航：`SOP.md`
- 指标口径与降级语义：`02_指标定义_SEC_10公司单年指标.md`
- 稳定 SEC/XBRL/证据原理：`docs/concepts/sec_xbrl_and_evidence_model.md`
- source/artifact provenance：`docs/validation_snapshot_provenance.md`
- 原始设计说明：`docs/history/sec_10_company_spike_original_design.md`

## 为什么降级

旧版本以 M0–M7 表达概念阶段，但当前物理实现是 `scripts/00_*` 至 `scripts/12_*`：stage 11 负责 bounded repair 与报告构建，stage 12 负责独立终态 gate 和 validation snapshot provenance。两套阶段不是一一映射。

旧版本还包含已废弃或不再权威的描述：

- `local_evidence_path`；当前 portable locator 是 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`；
- 未列 `evidence/requests_log_manifest.json`、`evidence/request_attempts/`、`outputs/validation_run_manifest.json` 与 provenance sidecar；
- 把 auditor changes 作为通用 8-K 用途；当前 C04 权威机制是 current/prior 10-K 官方 DEI `AuditorName` 重放；
- 把 Golden 描述成独立于计算脚本的现状；当前实现仍集中在 `sec_pipeline.py`，这是待拆分的架构债务而非已实现边界。

因此 M0–M7 只能作为历史业务方法阶段理解，不能用于操作脚本或验收当前结果。

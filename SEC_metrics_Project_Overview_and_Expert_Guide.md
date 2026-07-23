# SEC_metrics 项目总览导航

> Status: active navigation page
> 本文件不保存动态测试数、validation row 数、mismatch 数、代码行数或当前 verdict。

## 稳定原理

读取 `docs/concepts/sec_xbrl_and_evidence_model.md`，了解：

- SEC submissions、companyfacts、accession materials 三个数据平面；
- XBRL concept/context/dimension/unit/scale；
- companyfacts-first、accession-aware 的计算路径；
- portable locator、request ledger、数值与事件证据链；
- C04 AuditorName 与 8-K exact-set 的稳定语义。

## 当前运行状态

按以下顺序读取：

```text
outputs/validation_run_manifest.json
→ python3 tools/check_validation_snapshot.py
→ outputs/validation_snapshot_provenance.json
→ REPORT_十公司财务指标.md
→ outputs/repair_validation_results.csv
```

任何根目录 Markdown 中的历史结论都不能替代这些 artifact。

## 架构与操作

- 架构：`architecture.md`
- 当前能力边界：`capability_contract.json`
- 用户可观察行为：`interact.md`
- 执行命令：`README_RUN.md`
- 测试与 full/light 边界：`TESTING.md`
- 标准流程：`SOP.md`

## 历史快照

Round-3 的历史测量说明见 `docs/history/round3_snapshot.md`。原始长篇指南可在该文档标注的固定 commit 中读取；其数量和结论不是当前状态源。

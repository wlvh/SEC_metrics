# SEC 十公司 spike：原始设计简报

> Historical snapshot
> Source: repository root document before the validation-provenance refactor.
> Reference commit: `2d3f1381a6cb1b8c90bf2127a6f7093fc8ced0bc`.

这份历史设计使用 M0–M7 描述概念阶段，并曾使用 `local_evidence_path`、把矩阵/Golden/repair/report 合并在 M7 中，以及把 auditor changes 列入通用 8-K 用途。它反映了项目早期方法设计，不对应当前 `scripts/00_*`–`scripts/12_*` 的物理阶段，也不再定义 portable locator、request-log manifest、validation manifest 或 C04 权威重放路径。

保留该记录的目的，是让 reviewer 理解为什么当前文档体系明确区分：

```text
概念方法阶段
物理执行阶段
当前状态 artifact
历史测量 snapshot
```

需要原始全文时，请查看上述固定 commit 中的 `01_SOP_SEC_10公司单年指标计算_直接SEC.md`。当前执行和口径分别以 `README_RUN.md`、`SOP.md` 与 `02_指标定义_SEC_10公司单年指标.md` 为准。

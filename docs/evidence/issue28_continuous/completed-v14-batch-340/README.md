# 固定版本十公司 × 34 项完整离线批次

实际执行版本为 `1c9f5621e4e09f891d597fa7edcea970a3d434dc`。批次于 2026-09-12 08:38:58 UTC 开始、11:37:26 UTC 结束，耗时约 178.46 分钟。全部 340 坐标唯一，逐个文件与最终 summary 一致；执行前后 318 个运行文件字节均未改变。

终态是 **COMPLETED_WITH_GAPS**，CLI exit 2：

- 287 个 OPEN 候选，53 个 WITHHELD 候选；没有输入或执行异常。
- 原生质量标志为 147 EXACT、134 N_A_STRUCTURAL、4 NOT_MEANINGFUL、2 APPROX、53 WITHHELD；EXACT 不意味着全部是数值指标。
- 336 份公共行准备成功。Marriott B06、Ford B07、Lumen B06、Lumen B07 因同一 NOT_MEANINGFUL 展示基线字段缺失而失败；其原生 Run 已存在，原始诊断保留。

`gaps.json` 从相应原始绑定补齐了 Company Facts 子指标的失败详情。来源问题、未实现的主体/修订处理和债务范围缺口保持分开，不能统称披露不足。

完整本地数据仍位于 `/tmp/sec_metrics_issue28_continuous/v14-ten-company-34-1c9f562`。`artifact-index.json` 对 3,108 个坐标、Run、展示文件及绑定文件记录 SHA-256；原代码和原始来源保存在上述 Git commit。本目录保留请求、完整总结、运行日志和首次展示失败。后续修复与重验另记，不覆盖这个批次。

所有 Run 均未冻结，新增 provider / paid / SEC 为 0 / 0 / 0；正式 active 未改。本批次仅覆盖已接入的 34 项，不代表完整 39 项、390 坐标验收或正式采纳。

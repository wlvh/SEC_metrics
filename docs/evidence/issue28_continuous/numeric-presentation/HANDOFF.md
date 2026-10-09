# 普通数值展示组件检查点

仅新增 normal_numeric_projection.py、normal_numeric_projection_v1.json 和对应测试，既有 Spec/金融组件/Run/规则/CLI 未修改。

## 实际覆盖

- 六项 JPM 金融原件，Marriott C03/C04、Marriott B06 非正权益，以及 Salesforce A03 结构性不适用。
- canonical ratio/USD/flag，既有 20/18 列 CSV；季度、时点与年度保持实际日期。
- 原件单元格 raw_text 和完整格定位保留；测试通过实际生产表解析器从保存的原件恢复六项金融值位置。C03 fact locator 与 B06 XML context/ordinal 也从原件重获。
- C04 TEST_ONLY 移除事件输入后，原生 resolver 返回 C04_EVENT_COVERAGE_REQUIRED；展示空值、WITHHELD、空 Evidence，保留具体 selection 原因与来源 URL/路径/摘要/申报范围。
- NOT_MEANINGFUL 的 Debt completeness: NOT_EVALUATED 限定至 B06_guarded_v3、其已执行 Spec 与实际 DENOMINATOR_GUARD trace；另一 B06 Spec 的空值拒绝套用该说明。
- value_raw 仅填写 resolver 保存的原文；没有直接数值单元格的推导 flag 或仅有原件 fact 定位的记录保持空白，value_normalized 独立保留真实观察值。
- 两个入口都不写源文件、Run、active 或发布；pure 接口即使收到 FROZEN 字符也不授源验证信用。

## 接口

`render_normal_numeric_run(data_root: Path, run_dir: Path) -> {row, evidence, receipt, files}`；files 包含 metrics_matrix.csv 和 metric_evidence.csv 的 bytes。公开入口实际调用 load_frozen_run 和 normal_run_v2.replay_case，再从不可变 Run binding 与重建 selection 渲染。其 receipt 才标识 FROZEN_RUN_VALIDATED/CANDIDATE_ONLY。

当前 8 项测试全部通过（56.633s）；尚未测试完整 V13 FROZEN 入口。按照 root 要求，等待 V13 草案稳定通知，未自行冻结。provider/paid/SEC=0/0/0，无正式采纳、发布或 active 切换。

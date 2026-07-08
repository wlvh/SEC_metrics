# Eleventh Company Behavior Fixtures

这些 fixture 验证扩展入口和 extractor 核心行为：新增公司样本应只改
配置或 fixture，不需要改 `scripts/`。

验收点：
- `industry_profile` 能挂载对应 extractor。
- lodging mock text 进入 `LodgingKpiExtractor` 后必须抽到 B10/B11，
  或诚实输出 `NOT_EXTRACTED` 且不崩溃。
- financial institution mock Basel pure ratio fact 必须抽到 A01/A02；当
  actual CET1 ratio 与 regulatory threshold 使用相同 preferred dimensions 时，
  A02 必须选择 actual ratio，不能选择 lower threshold。
- manufacturing mock captive segment debt fact 必须触发 B06 `NEEDS_REVIEW`。
- subscription mock RPO fact 必须抽到 B12，并保留
  `RPO != ARR; cRPO != ARR` 边界说明。
- 不用公司名、CIK、ticker、accession 或固定日期触发生产分支。

# 项目进度快照（接收方，v1）

范围：登记的 10 家公司 × 39 指标 × 各公司最近五个已披露完整财年（#47 §1 的原目标），共 1,950 格。沿用现有业务目标、验收标准与权限；本目录只汇总现状，不改任何业务结果、规则或旧状态。生成过程新增 SEC/模型/付费调用 0/0/0（运行时禁用网络，逐格记录的 `new_calls` 全为 0）。

汇总文字发在 [#153](https://github.com/wlvh/SEC_metrics/issues/153)；逐格事实以 `output/scope_table.csv` 为准。

## 文件

| 路径 | 内容 |
|---|---|
| `output/scope_table.csv` | 完整范围表，每行一个“公司 × 指标 × 财年标签”，共 1,950 行 |
| `output/summary.json` | 各类计数（参考分类、状态类别、核对比较、当期对齐、采纳、未能落格的核对记录等） |
| `output/history_rows.csv` | 本次实际使用的每条“当前 main 观察”（后续更新可直接复用，不必重跑） |
| `output/history_runs.json` | 每家公司运行的完成情况（完整导出 / 部分状态 / 未运行） |
| `output/manifest.json` | 输入路径、提交号、摘要与命令行 |
| `output/comment.md` | 发在 #153 的汇总文字（与已发布评论逐字相同） |
| `output/run_identity.json` | 冻结后逐格记录的程序身份与调用数核对（处理文件摘要与 main 一致、新增调用 0） |
| `inputs/periods/*.json` | 财年标签 → 选定年报与实际期间（生产期间选择函数在保存原件上的结果；未能解析的标签保留确切原因） |
| `inputs/content_checks.json` | 从 #47 PR52（`bcc0c0bc`）`docs/evidence/issue47_history/content-acceptance/` 抽出的逐格原件核对记录 |
| `inputs/previous-business-readings.json` | #47 statement pilot 的 60 格既有业务读数（含采纳编号） |
| `inputs/receiver_checks.json` | 接收方在合并记录中逐值核对过的格子（带原评论链接） |
| `inputs/adoption_records.json` | 仓库内找到的正式采纳记录（2026-09-10 PR40 批准） |
| `inputs/d02/` | D02 准备对照工具的输出与清单（50 个样本，加 Salesforce FY2026） |
| `inputs/links_v1.json` | 汇总文字中的固定链接、补件请求链接与说明句（`render_summary.py` 的输入） |
| `scripts/` | 生成脚本，见“复跑” |

## 列的含义（`scope_table.csv`）

- **范围**：`fiscal_year_label` 为发行人财年标签；`period_start`/`period_end`/`period_days` 为选定年报的实际期间（起始日 = 上一份选定年报截止日的次日）；`target_accession`、`amendment_accessions`、`reporting_cik`、`registrant_role`（Paramount FY2021–2024 为前身主体 813828，FY2025 为继任主体 2041610）。财年标签与实际期间分列，不互相替代。
- `current_view=Y`：该公司窗口内最近一年。当期成果是这些格的对应视图，不另计数。
- **参考分类**：`reference_class` 直接取 `catalog/reference/generated/sic_metric_map.json` 的原始字段 `business_applicability`（APPLICABLE / CONDITIONAL / PENDING_CONFIRMATION / NOT_APPLICABLE，四类互斥，每格只属一类）；`in_reference_subset_1150=Y` 表示 APPLICABLE 或 CONDITIONAL。PENDING_CONFIRMATION 不并入适用子集，也不并入不适用。
- **当前 main 观察**（`obs_*`）：接收方在 main（`681b35d8`）上用公司入口 `tools/vnext_company.py run --period fiscal-years --source-root <保存原件>` 离线运行的结果。`obs_source`：`HISTORY_RUN`（运行结束后用入口 `results` 只读导出）、`HISTORY_RUN_PARTIAL`（运行未结束或被中止，读逐格检查文件 `latest-check.json` 与保存的结果行）、`HISTORY_ENTRY_NOT_CONNECTED`（历史入口对该指标没有处理接口：B13、C02、D03；D02 只有提供 `--saved-legal-reviews` 时、且一次一个期间才处理，本次未提供）、`NONE`（本次未取得）。
- **D02**：另取对照工具的准备结果：`d02_prep_outcome`（可准备请求 / 准备失败原因）与 `d02_saved_answer`（#47 账本里是否有请求编号完全对上的成功回答）。对照工具的候选版本 `30c3f94e` 与 main `681b35d8` 的程序差别只有两个 D03 文件，D02 准备不加载它们，所以等同 main 结果。
- **当期视图**（`pub_*`、`align_*`）：现行发布指针 `outputs/active_publication.json` 指向的发布包中同一公司、指标、**期间**的行；期间不同的行只在最近一年的格上注明 `ROW_FOR_OTHER_PERIOD:<截止日>`，不跨期比较。`align_status`：两边都有值时比较数值（`BOTH_VALUE_SAME/DIFFERENT`）；两边都是合理非数值终态时比较状态；其余写成 `PUB_<发布包状态>__CUR_<当前状态>`，状态取 `VALUE`（有值）、`TEXT`（发布包文字结论，文字在证据表）、`TERMINAL`（合理非数值终态）、`OPEN`（未出结果）、`NONE`（本次未观察）。
- `terminal_class`：状态类别（见下）；`registered_defects`：`docs/evidence/issue28_continuous/known_result_defects.json` 中同一公司、指标、截止日的登记错值；`pub_defect_flag`：发布包在这些格上仍有值（区分“与登记错值相同”与“登记未记录错值本身”）。
- **原件核对依据**（`original_check_basis`、`check_recorded_values`、`check_vs_current`、`check_sources`）：按公司、指标、截止日（或财年标签）对齐的既有核对记录，再与本次观察比较，不按结果编号继承。比较规则：
  - 数值按记录的小数位比较；没有读数、只有已发布值的记录，仅在核对结论为 `MATCH`/`MATCH_BOTH_BASES`（已发布值等于原件读数）时把已发布值当作读数；
  - 文字结果（D01、C02、D02）按记录的已发布文字 SHA-256 与本次文字的 SHA-256 比较，只有核对结论为 `MATCH` 的摘要算确认；
  - `SAME_VALUE` 才算沿用（`_DIFFERENT_FILING` 表示申报编号不同）；`DIFFERENT_VALUE_OLD_READING_HAS_REGISTERED_DEFECT` 表示旧记录核对的是后来登记为错值的数；`DIFFERENT_VALUE_DERIVED_FROM_B01_DEFECT` 表示由同年或上一年 B01 错值派生的 B02/B03；`NO_RECORDED_VALUE` 为没有可比读数的记录（`_CHECKED_VALUE_NOT_MATCHED` 表示记录的结论不是 MATCH）；`NO_CURRENT_VALUE` 为本次没有值。
- `adoption_status`（与原件核对分开）：`FORMAL_ADOPTION_2026_09_10`（PR40 批准中逐项采纳）；`ACTIVE_PUBLICATION_CARRIED_OVER`（在现行发布中、随发布整体继承，没有逐项采纳记录）；`NOT_ADOPTED`。
- `owner`、`next_step`：按状态类别给出的负责人与下一步。

## 状态类别

| 类别 | 含义 |
|---|---|
| `VALUE` | 本次观察有值（含事件计数 0） |
| `TERMINAL_NON_NUMERIC` | 结构性不适用、无经济意义等合理非数值终态 |
| `TERMINAL_NOT_DISCLOSED` | SEC 未披露 |
| `WITHHELD_BY_CURRENT_RULE` | 现行规则下的合理扣留（如 C04 缺上一年审计师事实、B02 前后期不可比） |
| `WITHHELD_CONFLICT_OR_AMBIGUOUS` | 原件内冲突或歧义，按规则扣留 |
| `KNOWN_DEFECT_WITHHELD` | 已登记错值，扣留 |
| `ANSWER_GAP_MODEL_RESPONSE` | 需要新的模型回答（额度由用户决定） |
| `ANSWER_GAP_NO_SAVED_D04_CALL` | 该年没有保存的 D04 回答（原因码 `HISTORICAL_D04_SAVED_SOURCE_MISSING_OR_AMBIGUOUS:0` 中的 0 = 账本里该年匹配数为 0） |
| `VALUE_PENDING_SAVED_ANSWER` | 已有能对上的保存回答，尚未经入口运行 |
| `INPUT_GAP_SOURCE` | 保存原件缺失 |
| `DEV_GAP_NOT_CONNECTED` | 历史入口未接入该指标 |
| `DEV_GAP_NAVIGATION_OR_PARSE` | 原件定位/解析缺口 |
| `DEV_GAP_AMENDMENT_OR_SUCCESSOR` | 修订年报/继任主体处理未接入 |
| `DEV_GAP_SOURCE_RELATION` | 来源关系或输入未解决 |
| `DEV_GAP_NA_REPORTED_AS_ERROR` | 行业不适用却以报错结束 |
| `NO_OBSERVATION` | 本次未取得观察（运行未完成） |

原因码到类别的映射写在 `scripts/build_snapshot.py` 的 `REASON_CODE_CLASS`；没有命中的组合落入 `UNCLASSIFIED`，不会被猜成某一类。

## 复跑

```text
# 0. 输入：main 检出（本版 681b35d8）、PR52 evidence/issue47_acquired 恢复的保存原件根
#    （文件摘要 sha256:a1975d77…，4,505 个文件；目录摘要 sha256:318f0ca6…）、
#    #47 账本 model-ledger.tar.gz（sha256 970c98e6…，PR52 bcc0c0bc 的 evidence/issue47_model_calls/9a368413797ddef1/）
# 1. 期间
python3 scripts/resolve_periods.py <main检出> <原件根> inputs/periods/<公司>.json <公司>
# 2. 当前 main 观察（每家公司一个新目录；不写旧状态；结束后自动 results 只读导出）
scripts/run_history_lanes.sh <main检出> <原件根> <账本> <输出根> 1 "公司…" 2 "公司…" …
# 3. D02 准备（main 上的对照工具）
python3 <main检出>/tools/compare_d02_preparation.py --baseline <main> --candidate <main> --source-root <原件根> --output-dir <新目录> [--companies salesforce --fiscal-years 2026-2026]
# 4. 既有核对记录
python3 scripts/extract_content_checks.py <仓库> bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786 inputs/content_checks.json
# 5. 生成表（--history-rows output/history_rows.csv 可代替 --history-root，复用本版观察）
python3 scripts/build_snapshot.py --code-root <main检出> --source-root <原件根> --periods inputs/periods \
  (--history-root <输出根> | --history-rows output/history_rows.csv) \
  --d02-comparison inputs/d02/cmp42a-comparison.json --d02-comparison inputs/d02/sf2026-comparison.json --d02-ledger <账本> \
  --publication <main检出>/outputs/publications/<现行发布包> \
  --content-checks inputs/content_checks.json --prior-readings inputs/previous-business-readings.json \
  --receiver-checks inputs/receiver_checks.json --adoption-records inputs/adoption_records.json --out <新目录>
python3 scripts/check_run_identity.py <main检出> <输出根> <新目录>/run_identity.json
python3 scripts/render_summary.py <新目录> inputs/links_v1.json <新目录>/comment.md   # 输出可直接发布
```

后续更新只需补跑未完成公司的第 2 步，再执行第 5 步；其余输入不变就不必重做。

## 限制（v1）

- 当前 main 观察未覆盖全部公司：运行按公司排队，本版冻结时完成的公司与部分运行见 `output/history_runs.json`；未取得的格标为 `NO_OBSERVATION`，后续版本补齐。JPMorgan 每个“指标 × 年份”约 3 分钟（其他公司约 20 秒），本版只取到 15 格。
- 4 份 #47 核对文件结构不是逐格记录，未解析：`b06-not-independently-readable.json`（说明为何无法独立读取）、`d02-both-directions-read.json`（无逐格结论）、`marriott-2025-statements.json`（已被替代）、`unread-value-triage.json`（分诊说明）。
- 发布包的文字结论（`TEXT_QUAL`）在矩阵中没有值，文字在证据表，本版未逐字比较，只标 `BOTH_TEXT_RESULT_NOT_COMPARED`。
- 当期视图只取现行发布包；#28 私有状态中的公司入口当期结果不在接收方环境中。

## v1.1（2026-10-14 12:44 UTC）

在 v1 基础上做有限修正，不重做范围：

- **补跑**：Ford、Southwest、Paramount、Marriott 已跑完，用原命令 `scripts/run_history_lanes.sh` 续跑。JPMorgan 用 `jpm_run.sh`，同样的参数，超时更长，仍在运行。
- **比较规则**：`build_snapshot.compare_checks`（测试见 `scripts/test_compare_checks.py`，运行 `cd scripts && python3 -m unittest test_compare_checks`）。
  - 值、期间、单位、主体、申报必须在同一条核对记录上同时相符；
  - 可用记录之间互相冲突时记为 `CONFLICTING_CHECKS`，不确认；
  - 读数等于已登记错值时不作依据（`NO_USABLE_CHECK_READING_IS_REGISTERED_ERROR`）；
  - 判定旧结果错、但原件读数与当前值相同的，记为 `SAME_VALUE_AS_CORRECTING_READING`；
  - 已声明的百分数和比率两种写法按换算后比较。
- **新输入**：
  - `--defects-file`：使用比观察代码更新的缺陷登记；
  - `--d02-side baseline` 配合 `inputs/d02/cmp44-main-fc0c9a45-comparison.json`：读取当前 main 的 D02 准备结果；
  - `--current-results inputs/current_results_v1_1.json`：#28 报告的当期 D04 结果，接收方未复现；
  - `--publication-errors`：`scripts/published_errors.py` 的输出。
- **发布出口错值**：`scripts/published_errors.py` 读取 active 发布包、根目录镜像与报告、缺陷登记，以及 #28 的数值核对。替代值按 `inputs/published_error_replacements.json` 从各公司原 10-K 的 XBRL 重算。

```sh
python3 -I scripts/published_errors.py --code-root <main检出> --source-root <原件根> \
  --value-checks <main检出>/docs/evidence/issue28_current_publication_read_20261014/source-and-publication-read.json \
  --replacements inputs/published_error_replacements.json --out <临时>/published_errors.csv
python3 scripts/build_snapshot.py --code-root <681b35d8检出> --source-root <原件根> --periods inputs/periods \
  --history-root <补跑根> --d02-comparison inputs/d02/cmp44-main-fc0c9a45-comparison.json \
  --d02-comparison inputs/d02/sf2026-comparison.json --d02-side baseline --d02-ledger <账本包> \
  --publication <681b35d8检出>/outputs/publications/publication_24bf8f… --content-checks inputs/content_checks.json \
  --prior-readings inputs/previous-business-readings.json --receiver-checks inputs/receiver_checks.json \
  --adoption-records inputs/adoption_records.json --defects-file <main检出>/docs/evidence/issue28_continuous/known_result_defects.json \
  --current-results inputs/current_results_v1_1.json --publication-errors <临时>/published_errors.csv --out output_v1_1
python3 scripts/render_v1_1.py output_v1_1 output "<冻结时间>" <main SHA> > output_v1_1/comment.md
```

实际参数记录在 `output_v1_1/manifest.json` 与 `output_v1_1/published_errors.json`。

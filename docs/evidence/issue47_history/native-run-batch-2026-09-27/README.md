# 全帧批次（2026-09-27）：12 个期间、454 个位置、零调用

**是什么**：已存目标原件的 12 个期间里，每个有路线的位置（已接线、结构性不适用、B13 定义范围外）都跑一次原生 Run；一个期间一个进程，一棵只读运行树，零模型调用、零 SEC 请求。

**跑的是哪棵树**：运行树逐文件核对等于提交 `51e01521` 加注册补丁（`../native-run-2026-09-18/0001-register-issue47-v1.patch`），closure `ad81126d…`。它**不是**当前 HEAD：批次之后规则文件与继承文件都动过，见下面"批次之后"。

## 文件

| 文件 | 作用 |
|---|---|
| `batch_plan.py` → `plan.tsv` | 从覆盖表自己的三条规则导出每个期间要跑的指标，不手写 |
| `run_one.sh` | 一个期间的驱动（安装、建 Run、冻结、公共行、另一进程冷读），调用 `../targeted-round-30a7934b/targeted_runs.py` |
| `batch_cleaner.py` | 冷读完成后删数据根（失败或冷读不一致的保留） |
| `merge_completions.py` + `completion.json` | 批次命令在 10 小时总超时处被截停（Paramount FY2024 停在 E05、Enphase FY2025 停在 A07）；半成品删掉，同标签同运行树在独立目录补跑其余位置，按计划顺序并回，`completion.json` 记下每行由哪次调用写出 |
| `report.py` → `measured.json` | 从批次矩阵、覆盖表与两份铸出的清单生成报告；遇到没告诉过它的理由码或失败类别就停，不把未知归进"缺口" |
| `name_version_releases.py` | 见"撤回的 21 个位置"；只在结果编号完全相同时为本版本命名已有修复的释放 |
| `compare_closures.py` → `later-closure-check.json` | 批次之后动过的指标在最终 closure 上逐位置重跑并与批次比对 |

## 结果（`measured.json`）

454 个位置全部尝试；440 个冻结出公共行，全部被另一进程冷读得到同一个运行与结果；14 个失败都已命名（12 个 D04 等所有者批准的模型审阅，2 个 Marriott 往年 C02 缺代理）。

- 数值 184（182 EXACT、2 APPROX）；结构性不适用 195；跑了没有值 61。
- 第三层：**184 个数值里 180 个被独立读过并接受，其余 4 个被开放缺陷撤回**（Lumen、Paramount FY2024、Paramount FY2025、Pfizer 的 D02：关键词代理或范围内容，修复要模型审阅，见 `../d02-item-8-review/`）。另一个撤回落在没有数值的位置上（Pfizer E01：新口径下按名扣留，旧缺陷点名的是另一个结果）。
- 已决政策拒绝 0（上一批 6，Part III 逐份准入生效）。

## 撤回的 21 个位置为什么变成 5 个

报告第一次生成时有 21 个位置被已登记缺陷撤回。逐个查：其中 18 个位置批次产出的**正是**已修复、已读过、已释放的那个结果（结果编号相同），只是释放记录点名的是更早的版本——缺陷登记的规则是"释放点名修复后的结果及其所在版本"，所以同一个结果在新版本下仍被撤回。这正是 `26017bed` 为 12 期间批次做过的事：同一结果在新版本下重现，就为该版本单独命名释放。`name_version_releases.py` 只做这件事，并且只在三处（Run 目录、行收据、矩阵行）的结果编号、运行编号与 closure 一致时做；开放缺陷（没有任何释放）不动，释放过但本批次结果不同的坐标（Pfizer E01）不动。共为 closure `ad81126d…` 命名 19 条释放（18 个位置；Pfizer D02 的同一结果被两条已修复的缺陷点名）。其中 Pfizer 与 Lumen 的 D02 仍被开放缺陷撤回，Salesforce B03 是按名扣留、没有数值，所以撤回 21 → 5，第三层 165 → 180（C02 10 个、D01 4 个、Enphase D02 1 个）。

## 跑了没有值的 61 个位置

| 类 | 个数 | 说明 |
|---|---|---|
| 关于公司的答案 | 12 | 分母非正、分子非正、接续注册人首期 146 天、主体不可比 |
| E01 等内容确认 | 7 | 有候选条目的窗口在登记确认前按名扣留（调用申请的 E01 授予） |
| 方法限制 | 2 | Salesforce FY2026 B03（D&A 覆盖范围无法由申报证明）；Paramount FY2024 C03（当年代理报告两位 PEO——Bakish 与 McCarthy——已批定义读的是单一 CEO/PEO 总额，不在两者之间挑选） |
| 具名缺口 | 40 | 见下表 |

具名缺口逐个查过原因（不是按理由码归类）：

| 原因 | 个数 | 位置 |
|---|---|---|
| 材料未存：往年财年窗口 8-K 正文与头文件 | 18 | Marriott FY2023、FY2024，Paramount FY2025（前身 9 份 8-K）的 C01、E01–E05 |
| 材料：最近一次请求失败的 8-K 头文件 | 7 | Salesforce FY2026 的 C01、E01–E05、C04 |
| 材料未存：accession 材料 | 6 | 上一期的：Marriott FY2023 的 B02、B03、C04，Marriott FY2024 的 C04，Paramount FY2024 的 B02；本期自己的 `index.json`：Marriott FY2023 的 B06 |
| 材料未存：代理 | 2 | Marriott FY2023、FY2024 的 C03 |
| **本 Issue 移植错误，已修** | 2 | Southwest FY2025、Paramount FY2025 的 C04（见下） |
| B06 债务关系无法证明 | 3 | Ford（已批工业范围：申报不报工业归母权益）、Southwest（供应商融资项目与债务的关系未证明；规则要求不自动扩建隐性债务重分类）、Pfizer（普通链路兜底解析器自己标 `IMPLEMENTATION_GAP`，与 #28 共有，不在 #47 单独分叉修复） |
| B06 修订影响未证明 | 1 | Paramount FY2024：B06 自己的修订检查读不了该份 10-K/A 的说明排版。**实测**：在探针进程里把"修订影响已证明"站进去（不写任何文件），级联停在 B06 债务关系无法证明——所以决定它有没有值的是债务关系，不是修订 |
| Paramount FY2024 C04 | 1 | 修复前停在同一个移植错误；修复后停在前身上一期 accession 的 `index.json` 未存（材料） |

**C04 的移植错误**：冻结的 `resolve_c04` 把 `current_filings` 读作"目标，然后是原始报告回退"，第一份不是目标就拒绝（`C04_FILED_TARGET_MUST_BE_FIRST`）。普通路线把链条第一份（有修订时是最新的 10-K/A）作为目标；历史路线传的是原始 10-K 的编号，于是每个带 10-K/A 的期间都停在这一步。普通路线对同一份材料：Southwest FY2025 发布 0（EXACT），Paramount FY2025 按名扣留 `C04_COMPARABLE_AUDITOR_FACTS_MISSING`。修法是一个表达式，与普通路线相同；新用例逐字段比对两条路线在两个期间上的答案，把目标改回原始 10-K 的注错只被这一条抓到。

## 批次之后

- 规则文件：新增 `historical_counted_calls.py`、`historical_legal_review.py`，改动 `historical_ma_confirmation.py`、`historical_results.py`、`historical_run.py`、`historical_semantic_results.py`、`historical_text_input.py`、`historical_text_results.py`，以及上面的 `historical_governance_results.py`（C04 修复）。
- 继承文件（两次 base 合并）：新增 `ordinary_processing_source.py`，改动 `capacity_native_assessment.py`、`continuous_sec_acquisition.py`、`continuous_semantic_calls.py`、`native_unit_index.py`、`ordinary_projection.py`、`ordinary_update_cycle.py`。历史路线里引用它们的只有语义路线（E01/D02/D04/B13 的 capacity 模块）、SEC 获取与普通更新；`historical_projection` 只从 `ordinary_projection` 导入 `POLICY_PATH` 与 `_claim_evidence`，两者自批次提交以来逐字节未变。
- 所以在最终 closure 上逐位置重跑的是 C02、C03、C04、D01、D02、E01、D04（12 个期间）与 B13（10 个期间）：最终 closure `b55afbac…`（运行树逐文件等于当前 HEAD 加注册补丁），结果在 `later-closure-check.json`：**94 个位置里 92 个与批次逐字段相同**（结果编号、值、质量、发布、理由码、错误、类别），80 个公共行全部被另一进程冷读得到同一个运行与结果。只有两处不同，正是 C04 修复的对象：Southwest FY2025 由扣留变为发布 0（EXACT），Paramount FY2025 的扣留理由变为普通路线的 `C04_COMPARABLE_AUDITOR_FACTS_MISSING`。14 个失败与批次相同（12 个 D04 等模型审阅、2 个 Marriott 往年 C02 缺代理）。已修复的结果在这一版本下也以相同结果编号重现，同样为该版本命名了 18 条释放（17 个位置）。Southwest 的新值由治理阅读独立读出（两年的申报都点名 Ernst & Young LLP，窗口内没有带第 4.01 项的 8-K）并接受，接受登记 184 → 185。在最终 closure 的这些位置上：51 个数值，47 个被独立读过并接受，4 个（D02）被开放缺陷撤回。这不是最终 closure 上的全帧：其余指标没有重跑，它们执行的规则文件未变、继承文件的改动只落在它们不调用的函数上。

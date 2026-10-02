# #54 固定实现 `e536cdca` 在 #47 历史入口上的核对 [shared-with-#54]

只记新增的接入、验证与阻塞，不代替五年业务验收。零 SEC / provider / paid 调用。

## 先更正一处

上一次核对（`../verify-2a642e56/`，#54 评论 5960340865）用的是 `2a642e56`。#54 在 #47 的评论 5957436385 于 18:49 被编辑为 `e536cdca`（PR55 head），我 19:55 发报告时没有注意到编辑，核对了较旧的版本。`e536cdca` 比 `2a642e56` 晚两个提交，其中历史运行树的编号改成了 `issue_54_v3`。所以这次在 `e536cdca` 上重跑同样的位置。

## 怎么核的

与上次相同，只换了 #54 的文件：

- **程序树**：本方 `9efceced`，加 `e536cdca` 的公司模块、`tools/vnext_company.py`、`tools/verify_company_bound_run.py`、测试文件和 `docs/company_compute_boundary.md`，共 19 个文件，逐个与 `e536cdca` 的 blob 相同。比 `2a642e56` 多了 5 个模块（`company_processing.py`、`company_processing_read.py`、`company_result_read.py`、`company_result_view.py`、`company_worker_guard.py`）。没有改本方文件。
- **准备端来源**：上次在这棵树里恢复并登记的整份取数会话（1,547 行追加）。
- **#54 的命令**：`export --history-years 5` → `install-runtime --kind historical` → `install` → `compute --report-end`。新的信任根、新的运行树、新的公司状态目录，上次的状态都已删除。
- **对照**：上次本方原入口在同一份代码（`9efceced` 加注册补丁、重新铸造）上建的 Run，记录在 `../verify-2a642e56/compare-*.json` 引用的矩阵里。本方代码没有变，所以可以直接对照。
- **读回**：`../verify-2a642e56/compare.py`，在另一进程里分两种方式读回：收据哈希检查（`read_run_receipt`，只核清单里三个文件的哈希）与原生冷重放（`load_frozen_run` 加 `render_historical_run`，从 Run 自己的数据根重推，行与证据字节和计算写出的比对）。汇总由 `../verify-2a642e56/summarize.py` 生成。

## 结果

| 步骤 | 结果 |
|---|---|
| 导出 | 两家都通过；检查点编号与上次相同（Paramount `a1e80ec1…`、Salesforce `f44aa0e8…`）。Paramount 706 秒、原件 81.1 MB；Salesforce 636 秒、原件 62.9 MB |
| 运行树安装 | 6.1 秒，`issue_54_v3` |
| 导入 | 34 秒、36 秒 |
| 计算 | Paramount 4 个指标 1,210 秒（上次 3,400 秒）；Salesforce 5 个指标 1,277 秒（上次 4,255 秒） |

**阻塞 1 已解决。** 运行树编号 `issue_54_v3` 合 `records.py` 的格式，Run 在运行树里直接建成，不再需要上次的改编号探针。

**阻塞 2 仍在**（`e536cdca` 早于上次报告，这是预期的）：Paramount FY2024 C01 在准备输入时报 `FileNotFoundError: <运行树>/evidence/accession_materials`。成因与上次相同，这次核实了细节：冻结的 `normal_zero_ai_results._event_sources` 要求数据根与程序根（`ROOT`）里旧式 `evidence/accession_materials/<公司>_<CIK>_<accession>/` 目录列出的窗口内 8-K **完全相同**。取数会话新取的文件存在不可变请求记录里，不在这些旧式目录中，所以本方数据根和程序检出在这里都只有同一份基线目录，比对相等（实测 Paramount 前身 FY2022 两边都是 0、FY2024 两边都是 22）。#54 的运行树不装原件，所以目录不存在；即使建一个空目录，两边也会不相等（`NORMAL_EVENT_ACQUISITION_CENSUS_DIFFERS_FROM_INSTALLED_INPUT`）。比对的"程序根"一侧在 #54 的设计里应换成已安装的公司来源（`<state-root>/source`）；本方历史事件遍历执行的就是这段冻结代码，会随之生效。

**通过的部分**：

| 位置 | 指标 | 与本方原入口比 | 收据哈希检查 | 原生冷重放 |
|---|---|---|---|---|
| Paramount FY2024（前身 813828） | B01、C02、D02 | 结果编号、期间选择、公共行哈希都相同 | 3/3 | 3/3：FROZEN、同一结果、行与证据字节相同 |
| Salesforce FY2023（历史分片里的目标行，非日历财年） | B01、B02、B12、C04、D01 | 都相同 | 5/5 | 5/5 |
| Paramount FY2024 | C01 | 停在阻塞 2 | — | — |

明细见 `summary.json`、`compare-*.json`、`steps-*.json`、`runtime.json`。临时目录路径已替换为 `<scratch>`。

## 性能

`e536cdca` 在 `compute_historical` 外加了本方的 `checkpoint_replayed_once`，计算快了约三倍（上表）。读回仍慢：`compare.py` 的读回进程不在这个作用域里，每个 Run 在新进程中完整重放检查点，约 5–7 分钟。这是本方核对脚本的做法，不是 #54 的问题；新进程从原件独立重推本来就是读回要证明的东西。

## 没做的

只核了两家各一期、8 个指标；没跑 E01–E05、D04、B13；没做内容验收；没测普通运行树。阻塞 2 修好之后，在同样的位置补核 C01 与 E01–E05。

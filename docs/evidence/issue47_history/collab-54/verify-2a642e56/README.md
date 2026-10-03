# #54 固定实现 `2a642e56` 在 #47 历史入口上的核对 [shared-with-#54]

按 COMPANY-SEPARATION-v2.1，#54 主实现公司交接物，#47 核对自己的历史消费者。这里只记新增的接入、验证与阻塞，不代替五年业务验收。零 SEC / provider / paid 调用。

## 怎么核的

- **程序树**：本方 `9efceced`，加 #54 `2a642e56` 的 7 个公司模块、`tools/vnext_company.py`、`tools/verify_company_bound_run.py` 和两个测试文件（只加文件，不改本方文件）。
- **准备端来源**：在这棵树里用本方 `tools/vnext_historical_sec.py restore` 从 `evidence/issue47_acquired` 恢复整份取数会话（1,547 行追加，原冻结验证器通过后登记在这棵树里）。
- **#54 的命令**（`docs/company_compute_boundary.md`）：`export --history-years 5` → `install-runtime --kind historical` → `install` → `compute --report-end`。
- **对照**：同一棵树打上本方注册补丁、重新铸造快照，用本方 `period-batch/period_runs.py` 在完整恢复根上建同样位置的 Run（本方原入口、同一份代码）。
- **选的位置**：Paramount FY2024 是前身注册人的年度（主体切换、前身 8-K 窗口、Part III 修订件由代理申报方提交）；Salesforce FY2023 的目标年报行在历史分片里，且是非日历财年。

## 结果

| 步骤 | 结果 |
|---|---|
| 导出 | 两家都通过，三类声明都没有限制。Paramount 178 项依赖、原件 81 MB；Salesforce 136 项、63 MB；各约 11–12 分钟（两个进程并行，含声明框架规划） |
| 运行树安装 | 6.7 秒，`issue_54_history_v1` |
| 导入 | 各约 34 秒 |
| 计算 | **每个历史指标都在建 Run 的第一步失败**，见阻塞 1 |

### 阻塞 1：历史运行树的 Requirement 编号不合格式

`run_store.create_run` → `records.validate_record(manifest)` 报 `Successor artifact Requirement identity differs`。运行树里的 `records.py`（第 1866–1872 行）要求后继产物的 Requirement 编号匹配 `issue_[0-9]+_v[1-9][0-9]*`，而 #54 历史运行树的编号是 `issue_54_history_v1`。普通运行树的 `issue_54_v1` 合格式，不受影响。失败之前，期间选择、输入准备和数据根安装都已通过（失败的尝试目录里数据根完整、Run 目录只有空记录）。

**探针**（`probe_rename_identity.py`，只在运行树副本里做，不是 #54 的实现）：把编号统一改成合格式的 `issue_54_v2`，同步更新授权里这 7 个文件和校验器的哈希，其余不动。改后这一处即通过，下面的结果都在探针运行树上得到。探针运行树另外带着两个 `.pyc`（改授权时导入 `canonical` 留下的），没有检查读它们。

### 阻塞 2：事件指标读程序检出里的原件清单

Paramount FY2024 C01 在准备输入时 `FileNotFoundError: <运行树>/evidence/accession_materials`。位置是 #28 冻结的事件遍历 `normal_zero_ai_results._event_sources` 第 121 行：`_acquired_event_filings(repo_root=ROOT, ...)` 把数据根里已取得的 8-K 头文件清单与**程序检出**下 `evidence/accession_materials` 的清单比对，要求相同。#54 的运行树按设计不装任何 SEC 原件，所以这里找不到目录。本方原入口不受影响，是因为程序检出本身带着基线原件。

- 本方历史事件遍历（`historical_event_walk.py`）执行的就是这个冻结函数的代码对象，所以 C01、E01–E05 都会停在这里。
- 同一函数也是 #28 普通路线的事件遍历，普通运行树的 C01/E01–E05 应同样受影响——这一点只读了代码，没有实跑。
- 这次比对的用意是：数据根带的已取得头文件不能比权威来源少。计算端没有程序检出里的原件之后，它要锚定在别的东西上；在 #54 的设计里，合理的锚点是已安装的公司来源（或信任根里准入记录点名的文件）。这需要定一个实现方。

### 通过的部分（探针运行树）

8 个指标在公司包路径上建成 Run。逐个与本方原入口在同一份代码上建的 Run 比对，并在另一个进程里分两种方式读回：**收据哈希检查**（`read_run_receipt`，只核清单里三个文件的哈希）与**原生冷重放**（`load_frozen_run` 加 `render_historical_run`，从 Run 自己的数据根重推，行与证据字节和计算写出的比对）。

| 位置 | 指标 | 与本方原入口比 | 收据哈希检查 | 原生冷重放 |
|---|---|---|---|---|
| Paramount FY2024（前身 813828） | B01、C02、D02 | 结果编号、期间选择、公共行哈希都相同 | 3/3 | 3/3：FROZEN、同一结果、行与证据字节相同 |
| Salesforce FY2023（历史分片里的目标行，非日历财年） | B01、B02、B12、C04、D01 | 同上，都相同 | 5/5 | 5/5 |
| Paramount FY2024 | C01 | 停在阻塞 2 | — | — |

Paramount 的 C02 取自前身那份由代理申报方提交的 Part III 修订件，包里带着；Salesforce 的期间由历史分片里的行选出。明细见 `summary.json`（`summarize.py` 从 `compare-*.json` 生成；比对与读回脚本是 `compare.py`）。临时目录路径已替换为 `<scratch>`。

## 性能（不阻断）

公司包路径每个指标 14–18 分钟（Paramount 4 个指标 3,400 秒，Salesforce 5 个指标 4,255 秒）；本方批次驱动在同一份代码与完整来源上，一个期间 8 个指标约 17 分钟。剖析一次输入准备（Paramount B01，170 秒）：73 秒花在公司准入校验，每次校验把该公司 114 个取数证明逐个重验，每个证明又把整本 2,532 行请求账本重新解析一遍，一次准备做 4 次。本方 `period_runs.py` 打开的推导缓存与 XBRL 解析块可以直接用在 `compute_historical` 里；重放块针对的是原取数检查点，不适用于公司准入。

## 没做的

只核了两家各一期、9 个指标；没跑 E01–E05、D04、B13；没做内容验收；没测普通运行树。

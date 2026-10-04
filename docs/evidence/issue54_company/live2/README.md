# Marriott 重新建立的真实任务（2026-10-04，live2）

这是一次**新的真实采集与运行**，不是恢复 10 月 3 日的原现场。原 31 次请求、旧 Run/结果/证据保留原身份；本目录的账本只记录本轮的新请求。新的来源版本和 Run 编号与旧的不同，没有为匹配旧编号修改任何记录。

执行位置：Claude Code 云端容器，Linux，root UID，工作目录 `/home/user/work/live2/work`、输出 `/home/user/work/live2/outputs`。不是 UID1000 原工作区、用户本机或 OpenShift。HTTPS 经环境出口代理，使用该代理的 CA 做正常 TLS 验证。程序为 PR55 `83db2c02`（当时 head `4ab93a54`，产品代码相同）自动安装的固定树。

## SEC 调用与预算

授权：累计上限 120 次 GET，原已记录 31 次计入，本任务固定额度 `--sec-allowance 89`（[承接记录](authorization-carryover.json)；只承接预算，不重建原账本）。

| 运行 | 新 GET（成功/失败） | 原件复用 | 新 Run | 冷读通过 | 总耗时 |
|---|---:|---:|---:|---:|---:|
| 首跑 `20261004T131606Z-add50227` | 29（29/0） | 0 | 36 | 36/36 | 1906.597s |
| 复跑 `20261004T134949Z-8de76bb1` | 2（2/0） | 27 | 0 | 36/36 | 869.029s |
| 局部重入 B01/C01/D04，`--max-sec-requests 0` | 0 | 29 | 0 | 36/36（含保留行） | 460.804s |

本轮 **31 次 GET，全部 HTTP 200**；含原 31 次累计 **62/120**，剩余 58 次未使用。31 行 `retry_attempt=0`，最小请求间隔 2.058 秒，User-Agent 为项目配置值。provider/paid 0/0。账本：[requests_log.csv](requests_log.csv) + [manifest](requests_log_manifest.json)，逐条正文/headers 的 SHA-256 与大小见 [sec-source-index.json](sec-source-index.json)（29 个不同正文，收到正文合计 17,022,146 字节）。

分段耗时（秒）：首跑 acquire 239.580 / handoff 7.372 / install 0.864 / compute 1247.391 / 冷出口 402.929；复跑 36.489 / 8.241 / 1.348 / 421.319 / 401.561；局部重入 8.666 / 8.439 / 1.382 / 41.840 / 400.258。宿主非独占，不外推到其他公司。

原文确认 FY2025（2025-01-01 至 2025-12-31），10-K `0001048286-26-000007`，2026-02-10 申报。

## 39 项结果

| 类别 | 数量 | 指标 |
|---|---:|---|
| 数值、标志、事件计数 | 18 | B01 B02 B03 B04 B05 B07 B08 B09 B10 B11、C01 C03 C04、E01–E05 |
| 文字 | 2 | C02、D01 |
| 结构性不适用 | 15 | A01–A13、B12、B13 |
| 不可比较 | 1 | B06 NOT_MEANINGFUL |
| 规则暂停 | 1 | D02 `UPDATE_D02_V2_CATEGORY_RULE_VALIDATION_SUSPENDED`（#28） |
| 未实现 | 1 | D03 IMPLEMENTATION_GAP（#28） |
| 待判断 | 1 | D04，旧判断与当前来源严格等价被拒（下节） |

36 个候选全部 `REPLAY_VERIFIED_CONTENT_NOT_ACCEPTED`：已经独立冷读验证，但**没有业务接受或发布**。与 10 月 3 日原运行相比，39 行中有 38 行的状态、数值、期间、申报号完全相同；D04 由"未配置处理输入"变为"已配置但等价被拒"。Result ID 有 17/36 相同（15 项 N/A 加 B01、B03），其余 19 项数值相同但 Result 绑定了本轮新的来源引用。复跑与首跑的 39 行状态、数值、Result 完全相同。

CSV：[首跑矩阵](first/metrics_matrix.csv) / [证据](first/metric_evidence.csv) / [摘要](first/run_summary.json)；[复跑](repeat/)；[局部重入](partial/)。

## D04：严格等价不成立

已配置旧 LIVE 处理包 f252a7a4、原 V14 程序、原基线 SEC 版本（`1b436ef0…`）及各自独立信任。现有接口完成认证，然后在当前来源上执行原程序的 `source_equivalence`，结果为 `UPDATE_NATIVE_SUBSTANTIVE_SOURCE_CHANGED`（[分析](d04-current-source-equivalence.json)）。

- 不等价的具体内容：同一 URL、同一申报的主 10-K `mar-20251231.htm`，原判断使用 2048661 字节/`c372495a`，本轮为 2048769 字节/`2068d818`。唯一的字节差异是 SEC 网站在 `</body>` 前注入的一个 `<script src="/ve5kkgOKS/…">` 元素（108 字节）。
- 17 个语义单元去掉原始字节派生的 ID 后，payload 完全相同，脚本没有进入任何单元。4 个原生请求在屏蔽 sha256 ID 后完全相同，但原始请求字节不同，因为原请求嵌入了由原始字节派生的单元/文档 ID，旧响应就绑定在这些 ID 上。
- 需要新判断或规则的原因：要复用，必须由 owner 批准"在派生身份前规范化 SEC 注入标记"的规则（Requirement/政策变更，属于 #28），或另行授权在当前请求上做新判断。本轮两者都没做：没有换来源、没有重签旧判断、没有调用模型。其余 36 项照常完成。
- 原 Result `e523b7a9` 在原基线来源上的复现继续有效（见 [d04-handoff-intake](../d04-handoff-intake/README.md)），原 WITHHELD/业务限制不变。

**更大范围的发现**：本轮 13 份 HTML 原件全部带有这类注入（`sec-source-index.json` 中的 `sec_bot_script_injected`），而 `0bc24734` 已提交的基线原件中没有一份带有。10 月 3 日原运行的 10-K 是另一个注入变体（2048784 字节/`06cb3fb9`）。SEC HTML 的原始字节已不再是稳定身份：凡是依赖原始字节身份的环节（保存判断的严格复用、新采集的"来源无变化"判断）都会受影响。是否引入规范化规则需要 #28 决定，本轮未改代码。

## 复跑与局部重入

- 复跑只刷新 2 份发现元数据，27 份原件 URL 复用，36 项 `NO_SOURCE_CONTENT_CHANGE`，没有新建 Run；Run manifest 总数始终为 36。
- 局部重入只请求 B01/C01/D04，单次上限 0 次 GET：元数据无法刷新，如实标为 `SOURCES_PARTIAL`，不报成功；B01/C01 为无变化，其余 34 行保留原有已验证结果并标 `NOT_REQUESTED`；D04 最新失败只更新 D04 自己的 `latest_failure`，不影响其他行。

## 交付材料

| 材料 | 内容 | 位置 |
|---|---|---|
| 最小计算交接包 `marriott-fy2025-company-compute-package.tar.xz` | 复跑导出的38指标公司来源包（`e94a8046`，原件+headers+账本+规则+准入）、其独立信任记录、D04 原基线 SEC 版本及信任、`processing.json`、三次运行输出 | 分支 `claude/brave-cori-zbxo2v` 的 `artifacts/issue54-live2/`，并作为会话附件发送 |
| 完整任务恢复材料 `marriott-fy2025-task-state.tar.xz` | 整个工作目录（不含可由 `export-results` 重建的 `result-exports`）：账本根与 31 次调用记录、全部 trust、固定程序树、36 个 Run 的 company-state、交接包 | 同上 |
| 完整性清单 `work-integrity-manifest.json.xz` | 打包前工作目录全部 128,009 个文件的 SHA-256 与大小 | 同上 |

存储提交 `6ebe8da7`（分支 `claude/brave-cori-zbxo2v`，路径 `artifacts/issue54-live2/`，已从远端重新克隆并通过 `sha256sum -c`）：

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| marriott-fy2025-company-compute-package.tar.xz | 5,461,496 | `10d5e21437f3ceea4d3fd5b20b41076bca35ec0bcdd31173ba0dcd538833db34` |
| marriott-fy2025-task-state.tar.xz | 14,039,596 | `ec43df9c82173f1b8e1882668d110eb4460ea6800a0d20ffc9cbb0029106e724` |
| work-integrity-manifest.json.xz | 419,180 | `9bb02a4a5c45f7982e86e91b343f95a1e9582ca03889df9bf9821c12f283ef45` |

恢复检查：完整任务包解压到新目录后，36,287 个文件与清单逐字节一致（坏/缺/多均为 0；被排除的 91,722 个 `result-exports` 文件可重建）。最小计算包在全新目录配合新装的 local 运行树（authority `792b5095`）完成 install，B01+D01 计算 83.602 秒，冷导出 27.618 秒；数值与 Result ID 均与 live2 相同。第一次打包时误用了局部重入的 3 指标包 `48a641a1`，计算 D01 被 `COMPANY_COMPUTE_METRIC_OUTSIDE_PACKAGE_SCOPE` 正确拒绝；已改为复跑导出的 38 指标包 `e94a8046`。

恢复说明见该分支的 `artifacts/issue54-live2/RESTORE.md`。继续原采集需要把任务目录放回绑定的绝对路径 `/home/user/work/live2/work`（账本 binding 和 Run 均记录了该路径），或明确登记重新挂载；不重签。D04 的处理包、原程序和原处理信任可以由 Git `7ed952bb` 的 `materialize-d04-handoff.py` 重建，不重复打包。没有提交任何令牌、密钥或私人凭据。

## PR56 集成

见 [pr56-integration/pr56-consumer-check.json](pr56-integration/pr56-consumer-check.json)。

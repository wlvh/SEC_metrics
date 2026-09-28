# Paramount D04 当前普通更新：限定独立审阅

结论：**PASS_WITH_BOUNDS**。审阅对象为精确提交 `3e1ba8b2c79d2be44b41e360772dd028b6906840`，比较基线 `77f00461cf7ec11f49a0bf8a9d02550184bb9aba`。在本次限定范围内，证据足以支持：原第179—188次真实成功响应已装入当前普通更新，形成新的 FY2025 私有 Run，并保留原 Result 内容身份；重复同一输入没有新建候选或增加原账本计数。未发现阻断此限定结论的问题。这不是全模块审阅、正式采纳或 GitHub APPROVE。

核对结果：

- 原 `finish-summary.json` 记录第179—188次、原 Run `097c5c92…`、Result `a185d849…`；原 `cold-summary.json` 将同一 Run 与 Result 绑定到持久候选，并记录独立冷读通过。当前安装的 schema 2 登记有十条对应序号，全部 `SUCCEEDED`、无失败请求；来源 ID 与原完成收据相同，当前输入登记 ID 和 Requirement 闭包则另有身份。
- 重跑 `verify-raw-identity.py` 通过。其代码逐条对比已安装登记与原账本调用：助手正文逐字节相同，来源、请求、intent、terminal 和 wire 按 JSON 内容相同；原 HTTP 响应文件哈希与 wire 记录相符，请求 ID、摘要与原批次摘要相符。十条证明保存在 `raw-identity.json`；复核输出见 `verify-raw-identity.log`。
- 当前 `result.json` 与安装 Run manifest 记录 `UPDATES_READY / CANDIDATE_READY`，Run 为 `5a2940f2…`，Result 仍为 `a185d849…`。私有公开行是 Paramount FY2025、`TEXT_QUAL`、空数值；`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE` 仅限规定范围内未见相应披露。行文件的 SHA 与当前收据一致；所存冷读在安装代码和输入副本上回放，当前私有历史 810 个文件前后无字节变化。
- 所存重复触发收据为 `NO_SOURCE_CONTENT_CHANGE`，成功指针仍指向首次当前 Run，`new_candidate_created=false`，首次成功包前后整树相同。首次及重复运行前后原账本均为 provider/paid/SEC `143/143/52`、195 行；首次运行另比较调用目录名及五项哨兵哈希，禁网钩子没有记录尝试。复核 `reconcile.py` 通过，输出见 `reconcile.log`。本次没有执行长时间普通更新、冷读或任何真实 provider/SEC 请求。

证据边界：首次运行只采样原账本计数、调用目录名和指定哨兵；原第179—188次调用目录及旧私有 Run 的**整树字节**没有在该运行前后完整采样。`verify-raw-identity.py` 证明复核时已安装内容与现存原调用内容相等，不能反推首次更新期间这些旧树从未变化。所存冷读的 810 文件哈希仅覆盖**当前私有历史**；重复检查的整树哈希仅覆盖**首次当前成功包**。`repeat-existing-real.py` 的 `new_real_calls` 字段为固定写值，零新增调用的实际支持来自前后账本计数与行数相同、首次调用目录名不变以及运行中的禁网限制；不能扩大为全局、跨进程没有请求的证明。同内容 Result ID 也不能单独替代新 Run 证明，故本次另核对了当前 manifest 与安装登记。没有新财年在线更新、正式发布、390 坐标新增或旧路径全面退出的证据。

执行的必要短命令：`python3 docs/evidence/issue28_continuous/d04-paramount-current-update-20260928/verify-raw-identity.py` 和 `python3 docs/evidence/issue28_continuous/d04-paramount-current-update-20260928/reconcile.py`，均退出 0。审阅仅写入本 `independent-review/` 目录；两条命令按其既有逻辑重写原目录中的汇总 JSON，重跑后它们仍与提交字节一致。工作树另有未提交的 `execution-state.json` 修改，未纳入精确提交审阅。本次累计 **38 次底层工具调用**（含写入本结论的调用），低于 80 次上限。

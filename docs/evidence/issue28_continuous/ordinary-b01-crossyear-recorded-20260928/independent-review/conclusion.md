# Marriott B01 跨财年录制演练：限定独立审阅

**结论：PASS_WITH_BOUNDS。** 对基线 `120e0e2be51c243556623f81556879c76bbfe071` 至精确补丁 `c0e95d3ac6adc8dd0f5034898a06bd2b1cc18f1b`，本审阅仅检查本证据目录及其明确复用、在该差异中未改动的 `c04-adjacent-year-rehearsal-20260927/rehearse.py`。证据支持 Marriott B01 在**构造旧时点清单→已保存真实新清单**的禁网录制条件下，由同一普通更新入口形成 FY2024 与 FY2025 两个不同的局部候选 Result/Run，并保留前驱与重复运行状态。范围内未发现与此限定结论冲突的证据。补丁另改动的全局进度文件不在本审阅范围内。

我执行 `PYTHONDONTWRITEBYTECODE=1 python3 -B docs/evidence/issue28_continuous/ordinary-b01-crossyear-recorded-20260928/reconcile.py`，退出 0，输出 `PASS_RECORDED_AUTO_METADATA_REFRESH_TWO_FISCAL_RUNS`；运行前后已提交的 `reconciliation.json` SHA-256 均为 `66e577d40dc5212395f9a15ee5bc79cbbfb28a214d4e884d43d5efb6ae5f9ffa`。另作只读字节、原始事实、账本、前驱及状态核对，结果在 [checks.log](checks.log)。没有重跑两个较长的安装冷读或录制链。

- `rehearse.py` 将 2026-02-10 起的 recent 申报行从真实保存的 SEC 清单裁掉；独立重算所得旧清单哈希为 `5b542458...`，与第 1 录制槽正文相同。它是**构造响应**，没有旧时点真实 SEC 返回的来源信用。第 2 槽正文 `e3eeefe3...` 与仓库保存的清单原字节相同；原请求日志记载 2026-09-08 HTTP 200、用途 `annual_update_submissions`。两个槽的 `execution_mode=RECORDED_TEST_ONLY`、`actual_sec_egress_count=0`。
- 首次旧清单由演练脚本显式捕获。第二次 `refresh_and_process` 只接收会话、公司、B01 和一次录制 SEC 配额，没有传年报 URL、财年或数值；它形成的请求计划及收据均指向 `https://data.sec.gov/submissions/CIK0001048286.json`，请求计划把第一次清单作为刷新前驱。执行脚本与 `/private/tmp` 实际运行副本逐字节相同。
- 两个成功终态及安装包分别绑定 FY2024、FY2025 原年报和 Company Facts；三类来源副本的哈希均与各自 Run 的 `source_references` 一致。原始 Company Facts 的 `us-gaap:Revenues` 事实按各自 accession、全年期间、USD 和 10-K 表单给出 `25,100,000,000` 与 `26,186,000,000`。Result ID 分别为 `c51c10da...`、`e279b28d...`，Run ID 分别为 `4e799f11...`、`bd73b6e9...`。新 intent 的 `previous_successful_attempt` 指向旧成功尝试；保存的两次安装冷读均退出 0、状态 `PASS`，且各自报告历史文件字节未变。本审阅核对了冷读日志、安装包与来源字节，没有独立重跑冷读。
- 当前状态的 `successful_attempt` 仍指向 FY2025 成功包；重复输入只新增 `latest_attempt`，终态 `NO_SOURCE_CONTENT_CHANGE`，无新候选，两成功包保持不变，录制计数前后均 `[0,0,2]`。前期失败日志和退出 1 原样保留，失败原因是测试错误地要求整个 `current.json` 不变；后续对账及最终重复检查均核对成功指针不变、最新尝试前进。

**证据边界：** 第一次清单和录制调用不证明真实在线时间序列；两期所需原年报及 Company Facts 都来自已保存材料。`real_calls=[0,0,0]` 还由录制收据的零外发及禁网脚本支持，不作为真实调用成功信用。两期 B01 局部候选均成立，但总体 `source_refresh=REFRESH_INCOMPLETE`、报告 `UPDATES_INCOMPLETE`；没有完整常态刷新、390 坐标验收、正式采纳或生产权限的结论。完整私有运行根位于 `/private/tmp/issue28-b01-crossyear-auto-20260928`，未随补丁入库；异机重跑 `reconcile.py` 需要这份运行根，本次审阅结论绑定于此机保存的原件。未改业务代码、未发真实 provider/SEC 请求、未操作其他 Issue/PR 或分支。

审阅使用 **32 次底层工具调用**，未触及 80 次和 90 分钟上限。

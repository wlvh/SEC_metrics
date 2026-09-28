# Marriott B01 跨财年录制演练：限定独立审阅

**结论：PASS_WITH_BOUNDS。** 对基线 `120e0e2be51c243556623f81556879c76bbfe071` 至精确补丁 `c0e95d3ac6adc8dd0f5034898a06bd2b1cc18f1b`，本审阅仅检查本证据目录及其明确复用、在该差异中未改动的 `c04-adjacent-year-rehearsal-20260927/rehearse.py`。证据支持 Marriott B01 在**构造旧时点清单→已保存真实新清单**的禁网录制条件下，由同一普通更新入口形成 FY2024 与 FY2025 两个不同的局部候选 Result/Run，并保留前驱与重复运行状态。范围内未发现与此限定结论冲突的证据。补丁另改动的全局进度文件不在本审阅范围内。

我执行 `PYTHONDONTWRITEBYTECODE=1 python3 -B docs/evidence/issue28_continuous/ordinary-b01-crossyear-recorded-20260928/reconcile.py`，退出 0，输出 `PASS_RECORDED_AUTO_METADATA_REFRESH_TWO_FISCAL_RUNS`；运行前后已提交的 `reconciliation.json` SHA-256 均为 `66e577d40dc5212395f9a15ee5bc79cbbfb28a214d4e884d43d5efb6ae5f9ffa`。另作只读字节、原始事实、账本、前驱及状态核对，结果在 [checks.log](checks.log)。没有重跑两个较长的安装冷读或录制链。

- `rehearse.py` 将 2026-02-10 起的 recent 申报行从真实保存的 SEC 清单裁掉；独立重算所得旧清单哈希为 `5b542458...`，与第 1 录制槽正文相同。它是**构造响应**，没有旧时点真实 SEC 返回的来源信用。第 2 槽正文 `e3eeefe3...` 与仓库保存的清单原字节相同；原请求日志记载 2026-09-08 HTTP 200、用途 `annual_update_submissions`。两个槽的 `execution_mode=RECORDED_TEST_ONLY`、`actual_sec_egress_count=0`。
- 首次旧清单由演练脚本显式捕获。第二次 `refresh_and_process` 只接收会话、公司、B01 和一次录制 SEC 配额，没有传年报 URL、财年或数值；它形成的请求计划及收据均指向 `https://data.sec.gov/submissions/CIK0001048286.json`，请求计划把第一次清单作为刷新前驱。执行脚本与 `/private/tmp` 实际运行副本逐字节相同。
- 两个成功终态及安装包分别绑定 FY2024、FY2025 原年报和 Company Facts；三类来源副本的哈希均与各自 Run 的 `source_references` 一致。原始 Company Facts 的 `us-gaap:Revenues` 事实按各自 accession、全年期间、USD 和 10-K 表单给出 `25,100,000,000` 与 `26,186,000,000`。Result ID 分别为 `c51c10da...`、`e279b28d...`，Run ID 分别为 `4e799f11...`、`bd73b6e9...`。新 intent 的 `previous_successful_attempt` 指向旧成功尝试；保存的两次安装冷读均退出 0、状态 `PASS`，且各自报告历史文件字节未变。本审阅核对了冷读日志、安装包与来源字节，没有独立重跑冷读。
- 当前状态的 `successful_attempt` 仍指向 FY2025 成功包；重复输入只新增 `latest_attempt`，终态 `NO_SOURCE_CONTENT_CHANGE`，无新候选，两成功包保持不变，录制计数前后均 `[0,0,2]`。前期失败日志和退出 1 原样保留，失败原因是测试错误地要求整个 `current.json` 不变；后续对账及最终重复检查均核对成功指针不变、最新尝试前进。

**证据边界：** 第一次清单和录制调用不证明真实在线时间序列；两期所需原年报及 Company Facts 都来自已保存材料。`real_calls=[0,0,0]` 还由录制收据的零外发及禁网脚本支持，不作为真实调用成功信用。两期 B01 局部候选均成立，但总体 `source_refresh=REFRESH_INCOMPLETE`、报告 `UPDATES_INCOMPLETE`；没有完整常态刷新、390 坐标验收、正式采纳或生产权限的结论。完整私有运行根位于 `/private/tmp/issue28-b01-crossyear-auto-20260928`，未随补丁入库；异机重跑 `reconcile.py` 需要这份运行根，本次审阅结论绑定于此机保存的原件。未改业务代码、未发真实 provider/SEC 请求、未操作其他 Issue/PR 或分支。

审阅使用 **32 次底层工具调用**，未触及 80 次和 90 分钟上限。

## `ea557935ccae7ad01fcaab5042ef4dedbc4b288d` 增量审阅

**增量结论：PASS_WITH_BOUNDS。** 此节只审相对 `c0e95d3ac6adc8dd0f5034898a06bd2b1cc18f1b` 新增的 `*two*` 演练、`README.md` 增量、`reconcile-two.py` 与相应本机收据；上文对原补丁的字节与结论直接复用，没有重审。必要短命令 `PYTHONDONTWRITEBYTECODE=1 python3 -B docs/evidence/issue28_continuous/ordinary-b01-crossyear-recorded-20260928/reconcile-two.py` 退出 0，输出 `PASS_RECORDED_AUTO_TWO_SOURCE_REFRESH_TWO_FISCAL_RUNS`，提交的 `reconciliation-two.json` 运行前后 SHA-256 均为 `d13b0758041e1c141f1ad8b655d728bd65c25f0af8918f4998c44e5fdfa45f1f`。独立的只读核对见 [checks-two.log](checks-two.log)；没有重跑较长的录制与安装冷读。

- `run-auto-two.py` 为新期安装一个仅按控制器给出的 `url` 选择保存响应字节的录制路由；未知 URL 立即拒绝。路由随后调用事先保存的原 `session.capture(**kwargs)`，没有替代 `refresh_and_process` 的来源发现、请求计划、收据、来源登记或 Run。运行副本与入库脚本哈希一致。第二轮只传公司、B01 和 `max_sec_requests=2`，由控制器先后选出申报清单与 Company Facts URL；三个槽位各有含 `discovery_id` 的计划、真实执行的录制会话收据与终态。三个收据均为 `RECORDED_TEST_ONLY`、`actual_sec_egress_count=0`；槽 1 是构造旧清单，槽 2/3 分别是已保存清单 `e3eeefe3...` 和 Company Facts `af2fea71...` 原字节。
- 新期报告 `UPDATES_READY`、`REFRESH_CHECK_COMPLETED`，B01 为 `CANDIDATE_READY`；旧期报告仍为 `UPDATES_INCOMPLETE`。两期 Result ID 为 `c51c10da...` 与 `e279b28d...`；本次各自独立的 Run ID 为 `d0ff5340...` 与 `2d564ed7...`。两份安装包的原年报、清单和 Company Facts 来源哈希均与 Run 绑定；原始 `us-gaap:Revenues` 的期间、accession、USD 事实分别支持 25,100,000,000 与 26,186,000,000。新 intent 指向旧成功；保存的两次安装冷读均退出 0、状态 `PASS` 且报告历史字节未变。本审阅核对保存输出、安装包和原件哈希，未亲自重跑冷读。
- 同源重复后，成功指针仍为 FY2025 尝试，新增 `latest_attempt` 的终态为 `NO_SOURCE_CONTENT_CHANGE`，没有新候选，录制账本保持 `[0,0,3]`。重复轮设 `max_sec_requests=0`，总体如实回到 `UPDATES_INCOMPLETE`；因此新期的 `UPDATES_READY` 是**两项来源检查获准执行的这一轮**的状态，不能描述成以后任何无刷新轮次也保持总体 Ready。

**新增边界：** 第三槽 Company Facts 的响应哈希与请求计划中刷新前已知的来源哈希相同，它证明按控制器选择完成一次录制来源检查，未证明发现新的 Company Facts 内容。旧期录制根使用的是 FY2025 年报提交后保存的 Company Facts；只凭程序能选 FY2024 事实，不能推断旧时点曾真实持有该响应。旧清单仍为构造值，新期两项虽复制了真实保存字节，本轮并无 SEC 在线外发。`UPDATES_READY` 限于单公司 B01、已保存材料的两项录制刷新，不等于真实在线跨财年更新、十公司 39 指标验收或生产采纳。完整新运行根仍在 `/private/tmp/issue28-b01-crossyear-auto-two-20260928`，未随补丁入库；异机单靠提交无法重跑此对账。本轮只追加本节和一份短日志，未改业务代码。

增量审阅 **15 次底层工具调用**，两轮累计 **47 次**；均低于 80 次及 90 分钟上限。

# 4f57f9cb C04 续接待刷新集合回修限定独立审阅

审阅对象：`4f57f9cbfe51965e0e2a8949093a0d7bc2b85778` 相对 `8115b114b1de73627aece35c26ee3417e7f66846` 的新增差异；仅评估委托指定的刷新协调器、V14 manifest、续接测试、回修证据和当前接线收据。**结论：PASS_WITH_BOUNDS。** 上轮 `NEEDS_FIX_P2` 指出的“可改写前次报告的 `deferred_source_urls` 来扩大下一请求范围”已在当前真实第 193 槽上被拒绝。若 #28 只有一名执行者，并在申领前即时确认末槽仍为 193、累计仍为 `[143,143,50]`、来源日志摘要仍为 `6c5fa272fd25936bbcdb7fd344a0b25479c8c62da3edb7ef473ddaf4a659d4cf`，可以在原有受限权限内执行**一条** Marriott Company Facts GET。此结论不声称该 GET 已执行或成功。

## 判断依据

- `ordinary_refresh_cycle.py:163-175` 在核验前次真实槽收据、终态、来源日志和同一 C04 更新状态后，重新运行来源发现；用前次已取 URL 与来源日志中失败 URL 过滤，逐项比对报告的待刷新 URL 顺序和集合、`requirements_id`、发现状态、失败 URL 列表，并要求前次没有获取错误。`_Requirements.require()` 对已保存来源重验来源证明；`_pending()` 不把已失败 URL 当作可重取项目。改写报告单一字段不能再把旧申报清单放回许可集合。当前 C04 `source_proofs` 的交叉核对仍在申领前执行。
- 已提交的 117.000 秒录制日志 `resume-deferred-auth.log` 显示两次分别选择申报清单和 Company Facts，篡改、旧报告复用均拒绝；我只读取该日志，未重跑长测。我执行的 11 项 `tests.vnext.test_ordinary_refresh_cycle` 短测全部通过，输出见 `short-tests.log`。
- 我在当前代码下重新执行两项**只读**真实材料核验：原 `real-refresh-1.json` 通过 `_resume_one_c04_source()`，目标为 `https://data.sec.gov/api/xbrl/companyfacts/CIK0001048286.json`，角色 `companyfacts`；只给同一报告的待刷新列表追加前次申报清单 URL，则得到 `ORDINARY_REFRESH_RESUME_DEFERRED_SET_CHANGED`。见 `real-preflight.log`、`real-tamper.log`。两项前后均为 193 槽、`[143,143,50]`，新增真实调用 `[0,0,0]`。独立读取第 193 槽的计划、收据、终态，确认 Marriott 申报清单 `SUCCEEDED`、SEC 实际计数 1、终态 `[0,0,1]`；原报告与来源日志 SHA-256 分别为 `ca80ecee09f57099cf5a61eb0649b993f9b4e161821d4de429f9e56d65903955`、上述 `6c5fa...`。当前 `calls` 目录止于 `0193`。
- V14 manifest 中刷新文件的绑定 SHA-256/大小与当前文件相符。当前 provider、SEC、refresh 三份接线收据文件摘要分别为 `201745c1...`、`e4e94109...`、`c433e84e...`，均与已提交 `binding-summary.json` 相符；三者执行 authority hash 同为 `sha256:94cf9e4133cdc400ce4bca1aeec17343055e56a6c14188f33939c4b4af3e93c9`。真实只读预检还通过当前 `_check_session()`。刷新接线中的 SEC 授权器为 stub，不能用它证明第二条真实传输。

## 保留边界

`ordinary_refresh_cycle.py:260-269` 新增了在账本锁内复查前次 intent、累计和槽数，能拦住在初次快照后、该次复查前插入的 provider 或 SEC 槽。但复查后释放锁，来源日志摘要也在锁外比较，随后 `SecAcquisitionSession.capture()` 才另行持锁并申领；获取器内部没有接收“必须紧邻第 193 槽”的预期前驱。其他进程若在这段间隔申领，仍可能让续接落在后续槽位。这是**未观察到的并发风险**，不是原待刷新集合 P2 仍存在。上述唯一执行者和即时复查是本次一条 GET 的明确前提；若要支持并发执行，须在获取器申领所持的同一把锁内检查预期前驱与来源摘要。

本审阅没有发 SEC/provider 请求、没有重跑 117 秒录制、没有验证第二条真实 GET、并发压力、后续 C04 数值/公开结果或 390 坐标验收；未触碰 #47/PR52。精确提交以 `git rev-parse HEAD` 核对为 `4f57f9cb...`；工作树另有执行状态文件的未提交修改，本审阅没有读取它作为成功证据，也未改它。工具计数：17 次 `functions.exec` 编排、44 次内部工具调用，合计 61 次（截至写入本结论）。

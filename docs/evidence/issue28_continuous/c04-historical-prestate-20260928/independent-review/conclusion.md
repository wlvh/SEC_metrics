# b968a15f 定向独立审阅：C04 捕获前普通状态

**结论：PASS_WITH_BOUNDS（同一状态根由单个更新执行者使用的有限续接）。** 相对 `9fe1b34ef961d107bd18740d1a0cdad929a78189` 检查了 `b968a15ff5b2f3da62dcfcff2b5a7b745d8e680c` 的两处实现、两处测试、V13/V14 当前绑定及本目录证据。未发现单执行者路径中，单靠篡改前次报告、把实际 B01 结果降格为 `UPDATE_BLOCKED`，便能在新 B01 尝试已入账后取得第二次 SEC 捕获。此结论不授真实调用、跨版本历史写入或生产信用。

捕获前态在 `continuous_sec_acquisition.py:189-199` 于 SEC 槽申领前写入 `sec-plan.json`；它列出普通指标配置、当前指针、尝试目录名称及每个 intent/terminal 的字节身份，并带内容哈希。`intent.plan_id` 绑定整个计划，SEC terminal 的 evidence 又绑定计划文件字节。续接在 `ordinary_refresh_cycle.py:229-245` 核对最后一个 intent、计划哈希、前态哈希、公司、状态根和指标集合；在 `:297-334` 只有报告声称未尝试且当前历史状态与捕获前 B01 状态逐项相同、配置及当前指针可读时，才接纳已有 `current.json`/尝试目录。新建尝试或改变指针会失配。前次处理副本失败但 B01 旧指针未变，是允许继续的正例；缺配置而有指针不能由续接校验临时生成配置。原有报告已有实际 B01 terminal 时仍经 `:360-383` 与当前状态比对。

兼容边界也清楚：前态字段只在显式 C04 混合旧处理根路线传入；普通 `capture()` 默认参数仍为 `None`，旧 source-only 计划也无该字段。旧计划若没有前态，历史 B01 指针仍按旧保守规则拒绝，而无指针/无尝试的旧路径保持可读。当前 V13 闭包 `sha256:697c0216fc2099e2c18c2946d4a654f7bd0fe716ed8b2767fa82b1df0433dfa8`、V14 闭包 `sha256:1dff7e0e859bda416c94267680aa8b3d60552df4344cda0b5ac993e2f4c96456` 均由我在本机加载并通过当前执行文件校验；provider、SEC、ordinary-refresh 三份现行接线收据的执行哈希和各自 evidence 哈希也均吻合。`git diff --check` 通过。

我亲自运行指定短测：`PYTHONPATH=scripts /private/tmp/issue28_py314_venv/bin/python -m unittest tests.vnext.test_ordinary_refresh_cycle`，**14/14 通过**，日志为 [short-unittest.log](short-unittest.log)。提交者保存的 `material-final.log` 为单条真实保存材料的禁网录制测试通过，`regression-material.log` 为两条旧 C04 材料回归通过，`default-c04.log`/`default-sec.log` 为默认路线的录制检查；我只读这些长材料日志，没有亲自重跑或发 provider/SEC 请求。录制 ledger 中的模拟 SEC 数量不能写成真实账本新增。

**待保留的边界：** `ordinary_refresh_cycle.py:150-192` 的前态扫描及 `:321-334` 的续接比较未持有普通更新的 `update.lock`；`refresh_and_process()` 在 `:554-569` 只于下一次捕获前重核 SEC ledger/来源日志，没有重核普通状态。若另一个进程在比较后、第二次 SEC 申领前写入 B01 intent，第二次捕获可基于刚才的旧比较继续，新的 SEC plan 只会记录写入后的状态。因而这份补丁**没有证明并发同根写入安全**；如并发同根更新属于目标运行模式，应让普通状态检查与申领共享序列化机制，并增加有界并发/中断测试。本轮未做并发调度实测，也没有观察到真实额外请求。历史 B01 包在原安装代码根只读可回放是提交者另存的单包证据；当前 V13 配置会拒绝旧闭包，跨代码版本沿旧指针继续写入尚未获证明。#47 堆叠分支、真实新财年更新、完整 390 坐标与生产切换均不在本审阅结论内。

工具调用数：本审阅共 **30 次 `functions.exec` 外层调用、66 次嵌套工具调用**；无子代理、无真实 provider/SEC 请求。

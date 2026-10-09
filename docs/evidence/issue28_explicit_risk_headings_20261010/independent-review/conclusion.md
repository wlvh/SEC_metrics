# 656a1d3 显式 D01 后继接口限定独审

**结论：限定补丁通过；未发现需要修复的 P1/P2。** 本结论仅覆盖指定六份文件相对固定 base 的接口增量及其必要直属消费者；不授全 PR、真实财报内容、历史公司完整闭环、39 指标或生产信用。

- 受审 HEAD：`656a1d3c91a7599cab5127049b4b7f26f608d2fe`；base：`f6ef7886d6630f7675c25cd42e306c373ab05769`。
- 审阅目录：`/Users/lyuhongwang/.codex/worktrees/issue28-explicit-risk-headings/SEC_metrics`。
- 起止 UTC：`2026-10-09T22:32:25+00:00` → `2026-10-09T22:37:20.503679+00:00`（北京时间 2026-10-10）。
- 工具共 25 次：11 次外层 `functions.exec`、13 次 `exec_command`、1 次 `clock__curr_time`。普通消息共 3 条（2 条说明和 1 条最终报告），问题 0；未 spawn。
- 首次 git 工作树干净，HEAD 精确匹配；六份源码/测试/CI文件同时匹配提交 blob 和开发者 `tested-tree.json` 的 SHA-256。审阅结束再次验证，六份字节未变；新增持久文件只在本目录。

## 亲自执行的核验

1. 指定命令 `python3 tests/required_unittests.py tests.vnext.test_d01_explicit_running_headers tests.vnext.test_text_results tests.vnext.test_text_coverage tests.vnext.test_ordinary_current_update tests.vnext.test_history_company_dispatch`：88 项全部通过，失败/错误/跳过均 0；unittest 7.272 秒，命令总计 7.461 秒。Python 3.14.7。日志 `required-tests.log`。
2. 另外执行 6 个有限反例组，全部通过。直接执行 base 的风险选择器、text_results、D01 adapter 源码，对比本 HEAD 的默认和 V2 Candidate/Evidence：构造的粗体及下划线材料上，记录字段、id/hash 一致；默认风险 proposal 与 base 一致。V3 删除完整双 Parts 标题，保留带相同前缀的风险句及原始跨度；只剩页眉时拒绝形成空成功。缺 Item1A 的新绑定原件、降为默认/V2进行 Evidence 重放、主体/年度起止/期间/accession/原件字节/未知政策变化均拒绝。日志 `independent-counterexamples.log`。
3. 另外亲跑 3 项共用公司入口小探针，factory 和 controller 明确模拟：默认 D01 返回 `PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED` 且不调用 controller；显式 FY2024 + D01 每指标 factory 进入原 controller；没有选年却提供 factory 时拒绝。日志 `company-gate-counterexamples.log`。这些探针只证明准入与参数传递，未冒充真实 D01 计算或保存验收。
4. 首次公司探针使用了审阅脚本错误猜测的返回键 `metric_observations`，发生 `KeyError`；保存在 `company-gate-first-probe.log`，未计入通过。查明现有接口返回 `metrics` 后修正审阅脚本并执行上述 3 项，未修改产品或测试文件。

## 静态审阅与推断边界

- `risk_signals.py` 的新开关只接受真正的 bool，默认 False。新排除式使用 `fullmatch`，因而完整 `Parts I and II`（大小写/空白变体）可排除，`Parts I and II ...` 风险句不会被当作完整标签。句点与 ampersand 写法仍保留，符合既有明确有限页眉语义；未扩建分类器。
- `text_results.py` 的新增可选参数默认 False；所有旧外部入口继续用默认值。本次 base 对比是合成材料的直接执行，加上调用路径静态核验；未重跑历史大原件/全 Run。
- `d01_emphasis_results.py` 只在显式 `D01_EMPHASIS_SOURCE_V3_RUNNING_HEADER` 下给 Candidate 推导和 Evidence 重建传入同一个 True。默认仍委托冻结接口，V2仍使用 False。未知政策及错误 metric 拒绝；原件重建、主体/期间/章节及逐字跨度验证继续执行。已有 observation/result replay 将同一显式政策递送到 Evidence，这点是静态调用链核验。
- `ordinary_saved_result.py` 仅把 D01 加入 `EXPLICIT_CASE_METRICS`，没有加进 `SAVED_METRIC_IDS`。直属 `ordinary_current_update.run_once` 仍要求指定财年与 callable factory；`create_saved_result` 默认 D01 仍拒绝。共用 `company_current_records` 的默认创建也不进入计算；它允许检查既存显式 D01 保存记录，仍标示内容未获接受并保留既有确切缺陷扣留。该保存记录读取效果来自共用集合，未被误报为当前默认生产能力。
- CI 新增测试文件触发和 required-unittests 步骤，原 `scripts/**` 触发已覆盖四份产品文件。本次只静态核验 YAML 和亲跑其新增测试命令；没有运行远端 CI。

## 读取的先前证据及未覆盖部分

只读取父原目录 `collab-d01-running-header-20261003/independent-review-31beeab/conclusion.md` 确认原页眉语义与停点；其中大原件、404文件、151入口及长 CLI 结果属于先前报告，本次不重新授信用。开发者 README/日志/测试树用于定位与精确字节核对，开发者测试结果未冒充本次亲跑。

本次没有覆盖真实公司源选择、完整 PROCESSING_FILES、安装版本、实际历史 D01 company run/repeat/results、完整 native Run/Review/Calculator 或业务接受；这些仍由相应调用者完成。没有 SEC/provider/paid 请求、账户探针、#47 操作、产品/测试改动、commit/push、tar、合并、正式采纳、部署或 active 切换。上述通过结论不改变这些权限。

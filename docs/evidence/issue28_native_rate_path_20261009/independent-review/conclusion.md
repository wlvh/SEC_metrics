# 指定 SHA 限定独审

Verdict: **PASS（仅限本次系统 tmp 规范化、安装适配和小测试接线）**。

- Base: `e2d6784c9a464a04b793d3487e6e9868a37614b3`
- Patch / inspected HEAD: `a3e3e643aafd63b85561173177a6fbead2796a1b`
- 起始 UTC: `2026-10-09 06:52:06 UTC`（首次时间工具读数）
- 结束 UTC: `2026-10-09 06:57:37 UTC`
- 工具调用数: **31**，计入 functions.exec 包装及其嵌套工具；普通消息数: **3**，含开始、进度及最终报告。
- 按实时 Issue #28 2026-10-06 的可信内部工具前提审阅；没有恢复独立信任、防伪批准或全仓封存要求。

本范围未发现新增阻塞性缺陷。实际变更在 `Path('/tmp').resolve()` 完成系统路径规范化后才拼接 `sec-metrics-sec-rate-<uid>`，因此没有把用户限速子目录一并 resolve。子目录 symlink 拒绝、owner 校验、O_NOFOLLOW、目录 flock、共享 timestamp、原子写和 1 秒最小请求间隔均保持。TMPDIR 不参与 gate 选择。已独立运行子目录 alias / owner 负例。

`company_retained_local.py` 在 retained 8588 业务源码的临时副本内执行一次精确行替换；找不到唯一旧行时清楚失败。随后仍调用真实 `install-runtime --kind local`，不以现行程序假冒 retained 业务基线。独立实际安装 3.292 秒成功；已安装 helper 是 retained 原件加这一行替换，其 SHA256 为 `d76c7235789799dab1438155940c32d1718c9186f3b1c1d8e96a740ed255ed16`、size=14071，与新 `issue_54_v4/baseline_manifest.json` execution-authority 对应项严格相等。没有安装 SEC 原件；没有调用 SEC/provider/paid。探针临时 runtime 已清理，只保存安装日志。真实安装器内部沿用原来的临时 runtime Git 提交机制；没有对本工作分支 commit/push。

`prepare_program()` 的旧 task 分支先读取保存的 program_root 并返回；新增 installer 的哈希已属于新 task 的 program identity 输入。因此新平台适配会形成新程序版本，旧任务不被重装或重签。该实现、company runtime installer、CLI、当前 saved-source 入口和 SEC 配置都与 base 字节一致；指定旧任务保留、当前 source_root 分流测试通过。旧未修任务在 macOS 的原平台限制仍存在，需要后续显式迁移；这不是此次补丁承诺的自动修复。

实际测试与证据：

1. 独立执行 `TMPDIR=/private/tmp python3.12 -B -m unittest -v tests.vnext.test_native_rate_path tests.vnext.test_company_retained_local`，**7 项，0.322 秒，OK，零 skip**。日志 `small-tests.log`。
2. 独立真实双进程 probe：相同 UID，两个系统路径表示及不同 TMPDIR，实际进入同一物理 gate；第一个进程在 yield 内持锁 1.25 秒，第二个在 1.268860 秒后才进入。持锁时间超过 1 秒 timestamp 間隔，因此该结果同时证明内核锁排他与共享间隔，不能只由 timestamp 延迟解释。日志 `concurrent-rate.log`。测试 gate 位于独立临时目录，没有使用真实系统 SEC gate 或业务账本。
3. 独立真实 retained install probe 如上，日志 `install-probe.log`。5 个交付源/test/selector/workflow 文件均与作者 `tested-files.json` 哈希相同，最终 HEAD 与 tracked 工作树再次核实。
4. CI新增明确的 `python3 -m unittest` 步骤执行这两个 module，没有条件跳过；本机按相同两个模块实际执行成功。两模块在 v2 FAST_TESTS 各登记一次。特别核对：当前 `run_foundation_ci.partition()` 只继承旧 runner 列表，单独 v2 登记不会让它包含这两项；本补丁明确的额外 workflow 步骤正是实际 CI 覆盖。未声称 GitHub Actions 已有该 SHA 的终态；远端运行仍由父任务交付阶段核实。
5. 阅读作者的 README、install-probe、full-entry launch/results/summary、29 条 HTTP trace 和 `sitecustomize.py`。作者保存的完整链为 return 0 / FLOW_COMPLETED、159.595 秒，Marriott FY2025 B01=26186000000 USD、B02=0.04326693227091633466135458167 ratio，结果包含原件与期间身份，all_configured_business_metrics_completed=false。HTTP hook 仅用已保存 bytes，缺 URL / SHA / length 不符清楚失败，并禁止普通 socket connect / DNS。该 159 秒链**没有独立重跑**；该部分是对既有作者材料的检查，独立信用限于实际短安装及小测试/进程 probe。内部 LIVE/VERIFIED_SEC_ACQUISITION 字段是隔离测试产物，不是实际网络、真实来源获取或生产采纳证据。

本次无新 SEC/provider/paid，无账户、密钥或生产操作，无 #47 工作树/分支/账本/运行根访问，无长期演练或全链重跑。写入只限本目录的 conclusion.md 和三个必要日志。此 PASS 不覆盖全部39业务指标、真实 SEC 获取、Python3.14远端终态、合并、正式采纳或生产发布。

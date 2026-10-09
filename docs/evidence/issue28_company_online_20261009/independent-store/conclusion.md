# 来源根复用及录制模式的限定独立复核

结论：APPROVE_WITHIN_STORE_AND_RECORDED_INCREMENT。本次精确提交相对指定基线的来源根复用、不可变 URL 换任务限制、录制 HTTP 回复入口及 CLI 帮助文本，没有发现新增阻断项。受信任内部工具及普通误操作为本次前提；不授整 PR、财报业务数值、真实调用、生产、Ready 或合并批准。

- 精确 patch / 实际 HEAD：`d91489e39240a81d2a11527c2c293a0b307e6f68`
- 比较基线：`f1c0088d3a2069ea3ef98272f22349f738e88ef0`
- 开始 UTC：2026-10-09 03:43:15 UTC
- 完成 UTC：2026-10-09 03:50:13 UTC
- 实际工具调用：30 次，包含 10 次 functions.exec 外层及 20 次嵌套工具；没有其他工具。
- 普通消息：3 条，包含最终报告；问题 0；未委派子代理。

## 范围与继承

仅审 `scripts/vnext/company_online.py` 新增来源根配置、原成功 URL 的申领前检查、录制/LIVE 客户端分派；`scripts/vnext/recorded_sec_http.py` 的本地回复及原生落盘/日志路径；`tests/vnext/test_company_online.py` 的相关增量与 `tools/vnext_company.py` 帮助文本。必要时只读追踪原 SecHttpClient、CallLedger、saved_source 和任务身份/路径检查，不扩展为防伪、独立 trust 或递归 Requirement 审阅。

继承 `../independent-review/conclusion.md` 的已覆盖部分及 `../independent-p2/conclusion.md` 的 APPROVE_WITHIN_P2_INCREMENT；两个旧 P2 不重开，原失败及旧整体/计算阶段报告观察保持原义。新 `existing-store-cli.log`、`recorded-offline-chain.log` 只作现存开发证据检查；没有重跑原原件链，也没有把其完整财报/计算结果标为本代理在 d91489e 新验收。

## 本增量结论

`company_online.py:56–64` 按原 ledger.live 选择客户端。录制模式缺 `recorded_http_root` 当场拒绝；提供回复根时使用 RecordedSecHttpClient，不靠测试进程替换 urlopen 才避免真实网络。LIVE 分支在建立正常 SEC 客户端前拒绝该录制输入字段。该分支通过只有 live=True 属性的明确替身检验，未建立或访问真实 LIVE 账本，不将其扩大成真实 LIVE 执行证明。

`recorded_sec_http.py:13–35` 只从本地请求 CSV 的最新同 URL 回复读取原件，检查目录边界、长度和 SHA-256，并复用原客户端的持久化/日志方法。实际未替换 reply() 的正向测试成功落盘、产生原请求身份及模拟计数；urlopen、socket connect、DNS 三处计数全部为 0。缺回复及原件字节变化不会降级到 HTTPS，保留已申领 pending、SOURCES_PARTIAL 与具体原因；缺原件文件产生 status 0 / FAILED_TERMINAL / UNKNOWN_REMOTE_OUTCOME 并停止 SEC。最新 503 不回退到更早 200；200 带非空 error 也不写成成功。各失败仅一次模拟 claim，实际 SEC 次数 0。

`company_online.py:93–101` 在原账本锁内检查全部成功 SEC 槽的同 URL 原记录，再申领。换新来源目录时实际返回 ALREADY_CAPTURED_SOURCE_REUSE_REQUIRED，模拟次数仍 1、无 pending、原账本文件逐字节不变。同一完整来源根在另一 Capture/新任务中复用原不可变请求：原件字节、request_attempt_id、请求日志及原账本均不变。显式元数据刷新追加两个计数后，原请求行和 ID 有序前缀、原 ordinal 1 intent 保留，账本累计为 [0,0,3]。

`company_online.py:191–205` 固定 source_root 进入任务身份，使用原完整 SEC store，不裁行或重编号。实际新任务保存原来源身份并以 0 新 claim 复用原件；后来改变该任务 source_root 触发 TASK_IDENTITY_CHANGED，错误新来源目录未建立。代码根、其子目录/祖先、输出根及其子目录/祖先、状态根和 company-state 子目录八种重叠均在 Capture/申领前拒绝，原模拟账本不变。

CLI 实际 run --help 明示在线 call-context 只支持 B01/B02。现有 source-root 与 call-context 分派未改。本报告证明获取/存储/状态边界；新任务正向控制流使用明确合成 discovery，未运行财报计算，不赋予 B01/B02 内容接受。

非阻断文案观察：`company_online.py:5` 的旧模块注释仍称测试只替换 sec_http.urlopen；本增量测试及保存演练实际在 RecordedSecHttpClient.reply 处注入回复。该注释可随集中交付同步，不构成运行边界阻断。

## 实际验证与日志

原样短测试命令：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_company_online -v
```

`tests.log`：10 项，2.060 秒，OK，退出 0，无 skip。另在系统临时目录运行 20 个增量边界及全程网络拒绝检查，`boundary.log` 以 PASS_LIMITED_STORE_AND_RECORDED_BOUNDARIES 结束；7.365 秒，退出 0。夹具只使用明确合成 HTTP bytes 和临时 recorded ledger，本地原客户端持久化及 request_attempt_id 校验实际执行。只有新任务编排正向场景替换 acquire_financial；所有 reply() 原实现和错误场景未替换。

首次临时脚本遗漏 Archive URL 所需 accession，request binding 准确拒绝 Exact SEC response has no request-ledger attempt。该失败保留在 `boundary-initial.log`；随后仅修正内联合成夹具 accession 参数并重跑，未放宽程序检查或改源码。所有临时目录自动删除。

结束时 HEAD 仍为本报告精确 SHA；四个受审文件、两份继承结论与两份新开发日志全部与该 SHA 的 Git blob 相等，具体 SHA-256 见 `verification.log`。tracked 工作树和 index 无修改；本代理只新增本 independent-store 的 conclusion.md 及日志。没有实际网络/SEC/provider 调用、访问 #47 根/账本/许可、commit、push、源码修改、tar、长原件链或扩大旧 P2 结案。

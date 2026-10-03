# #54 固定实现 `191d1487` 在 #47 历史入口上的核对 [shared-with-#54]

只记这一版新增的适配、验证与阻塞，不代替五年业务验收。零 SEC / provider / paid 调用。

## 版本与范围

- 核的是 `191d1487`（#54 在 [Issue #47 评论 5965712264](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5965712264) 点名的固定提交）。它相对上一次核对的 `8a521e32` 只改了 11 个公司文件（`company_*.py` 与 `tools/vnext_company.py`），本方文件一个没动。
- #54 请求的是按"这处实际适配差异"审阅与验证消费者，不要求重跑已收到的 12 项业务材料，也不要求为新 closure 自动释放 D02。所以本次只做代码审阅加一个指标的端到端。

## 适配差异（读 `191d1487` 的代码）

1. 历史计算与另进程冷读复用本方三个块：`run_checks_replay_once`（检查点按账本状态只重放一次）、`derived_once_per_state`（派生缓存）、`xbrl_parsed_once`（XBRL 只解析一次）。
2. 安装出的运行树里，`ordinary_source_authority._validate_checkpoint` 与 `_trusted_checkpoint` 遇到公司准入记录（`COMPANY_SOURCE_ADMISSION_V1`）时转给 `company_source_authority`；`require_company` 在历史运行树里也改走 `_validate_checkpoint`，所以公司准入进了本方的重放缓存。
3. 只在 `--kind historical` 的运行树里，派生缓存把外部信任树（`SEC_METRICS_SOURCE_TRUST_ROOT`）同时加进缓存键的指纹和允许读取的集合。

## 审阅结论

- **检查没有被跳过。** 重放缓存包住的是安装后的分派函数，第一次遇到某个账本状态时完整跑一遍公司校验（信任记录比对加全部字节核对）。之后同一状态的调用拿缓存的答案，但每条读取路径在进缓存之前都会先调一次不经缓存的 `_trusted_checkpoint`：`verify_ordinary_source_proofs`、`checkpoint_installation`、`require_company` 三处都是如此，它把数据根导出的准入记录与信任树里的记录逐字比对。（`_validate_checkpoint` 另一个调用方是 `register_recorded_session`，它校验的是自己刚建、还没登记的录制检查点，不是公司准入记录，计算时不走。）缓存键（`normal_history_plan._replay_state`）包含检查点内容与数据根状态。所以信任记录被改或被删，下一次调用在缓存之前就失败。
- **一处低风险的记录，不是缺陷。** 重放缓存的键不含外部信任树；上面的结论靠的是"每个调用方都先调 `_trusted_checkpoint`"。以后若有新的调用方不经它直接调 `_validate_checkpoint`，在同一个块里拿到的缓存答案就没有重新核对信任。现有代码里没有这样的调用方。
- **派生缓存的改动成立。** 信任树进了指纹与允许集合，改信任会让缓存答案失效；环境变量缺失时 `memo_read_roots` 直接报错（不在缓存捕获的 `OSError` 里），不会退回不含信任树的键。缓存键本来就含全部环境变量的摘要，信任根换位置也会换键。
- **#54 自己的用例把分派整个替换掉了**（`test_historical_census_uses_existing_verifier_after_independent_trust_check` 模拟了 `_validate_checkpoint`），所以真实路径要靠端到端证明，见下。

## 端到端（Paramount 前身 FY2024，C01）

**程序树**：与上次核对同一棵（本方 `51250475` 加 #54 公司文件），只把这 11 个文件换成 `191d1487` 的字节（逐个与其 blob 相同）。

**#54 的命令**，见 `run.sh`：`export --history-years 5 --metric C01` → `install-runtime --kind historical` → `install` → `compute --report-end 2024-12-31`。

**一个操作细节**：`install-runtime` 从程序树的工作区复制文件，再在副本上打本方的注册补丁，所以执行这一步时程序树必须是未打补丁的状态。上次核对的程序树打着补丁，这次先暂存补丁、安装后恢复（`unpatched-status.txt` 为空、`repatched-status.txt` 列出原来的 7 个改动）。

**对照**：上次核对里本方入口在同一程序树、同一来源根上建的 Run（`../verify-8a521e32/compare-paramount-events.json` 的 `direct_path`）。

**结果**（`compare-paramount-2024-c01.json`）：

| 项 | #54 `191d1487` 路径 | 与本方入口 |
|---|---|---|
| 结果 | `96cf1530…`，PUBLISHED，值 9 | 结果编号相同 |
| 期间选择 | `6d66f921…`（前身 813828 的 2024 财年） | 相同 |
| 行哈希 | `b58a1f97…` | 相同 |
| 收据哈希检查（另一进程，`read_run_receipt`） | 清单三个文件的哈希通过 | — |
| 原生冷重放（另一进程，`load_frozen_run` 加 `render_historical_run`，不开任何缓存块） | FROZEN；行与证据的字节都与计算写出的相同 | — |

Run 编号与上次不同（`02144394…` 对 `11c8d0dc…`）：运行树的 closure 变了（`ef00c134…`），结果编号不含 closure。

**耗时**（`steps.txt`、`compute-paramount-2024-c01.json`）：导出 699 秒（一个指标、五年框架）、装运行树 5 秒、安装 35 秒、计算 143 秒（其中计算本身 111 秒）。上次 `8a521e32` 是六个事件指标 5,197 秒，每个约 14 分钟。另进程冷重放没有开缓存块，用了 475 秒。

## 没做的

- 只跑了一个指标。其余指标、期间没有在这一版上重跑；按 #54 的说明，计算逻辑没变，变的只是缓存与准入的接法。
- 信任记录或头文件被改时的负例由 #54 自己在做，这里没有重复。
- 没有跑 `results`，所以没有看到新增的 `CURRENT_RUNTIME_RELEASE_REQUIRED` 状态在本方登记上的样子。C01 在本方登记里没有缺陷，看不到这个状态；要看得用 D02 这类在别的 closure 下释放过的结果。

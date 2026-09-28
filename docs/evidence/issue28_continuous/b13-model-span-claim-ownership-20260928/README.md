# B13 V8 断言范围与归属：2026-09-28 限定回修

这是对 `b13-model-spans-v8-offline-20260927/independent-review/conclusion.md` 所列三个具体反例的回修；V8 仍是**暂停的离线候选**。本轮没有 provider、付费或 SEC 请求，没有 B13 完整公司结果，也没有解除 V8 真实执行或原生接受阻断。原 190 成功及 191/192 失败和次数均保持原身份。

## 改动与验收边界

- 一条模型范围同时罩住两个物理产能陈述时，记 `B13_MODEL_SPAN_MULTI_CAPACITY_ASSERTION` 未决；不把整句单个标签当成已解释现有产能和未来扩产。
- 对明确的逗号包围关系从句，主体判定不再把从句里“我们选择了供应商”的 `we` 误作主句“供应商拥有产能”的主体。
- V8 对由 `and` 连接、后项省略主体的谓语借用前项已明示主体，不再依赖少数动词开头。对本次已确认的 `and expect to add ... next year`，前项当前陈述形成有限的当前计划上下文；历史标签或排除类别与它冲突时给出具体未决。这个检查只覆盖可证明的必要冲突，不声称已理解一般英语指代和时态。

完整响应入口的新正反例包括：宽范围吞并、关系从句的错误/正确主体、合法分开的并列陈述、错误主体、错误历史期间及把扩产标成背景。测试只证实这些程序行为，不能证明模型会生成合格回答。V7 请求身份与此前保持一致；旧 V4/V7 接受规则没有改动。

## 实际验证

代码根：`/Users/lyuhongwang/Developer/SEC_metrics`。下列本地测试在提交前固定工作树执行，`fast-tree-before.json` 的六个源码/绑定文件哈希与最终工作树逐项相同；不能把它们冒充已提交 SHA 的远端测试。

- `targeted-module-final.log`：`tests.vnext.test_capacity_two_stage` 与 `tests.vnext.test_capacity_reference_contract`，36 项通过。
- `v7-identity-final.log`：V7 请求字节不变、没有新增 provider 许可。
- `binding-final.log`：当前未冻结 V14 执行身份，以及 provider、SEC、普通刷新三份离线接线收据通过；闭包 `sha256:79958e52a5cc0869f4610eb8bf6d49082a32749276d13f3936bb7de22abfefa8`。只同步当前 V14 绑定，不重签历史包。
- `fast.log`/`fast.exit`：最终工作树快速套件 135 个 selector 中 134 个通过；唯一未通过的 `tests.vnext.test_invocation_control` 在双作业并行、每 selector 30 秒限制下返回 124。该测试自己的子进程在 `join(timeout=10)` 后尚未退出，断言得 `exitcode=None`；目前证据不足以把它归因于本次 B13 改动，整套快速测试**不记通过**。
- `invocation-standalone.log`：同一最终工作树单独运行该模块 25 项，19.458 秒通过。它支持并行负载影响时间的解释，但不抹去上述失败；新提交的 CI 仍须按自身终态判断。

`red-test.log`、`red-time-kind.log` 保存新增回归在修复前的失败。`fast-pre-final.*` 和 `fast-before-time-kind-fix.*` 是中间树通过记录，均不作为最终快速套件证据。`rebind.py` 与前后身份记录保留可复算关系；没有重生成旧 MANIFEST 或打包旧材料。

`7676f49d` 的指定差异独审见下节；其 `NEEDS_FIX` 结论保留。V8 真实模型表现、完整原生公司链、190 的混合复用和新路线调用权限仍未获证或未获准。

## `7676f49d` 审阅发现后的同目录回修

`independent-review/conclusion.md` 对原提交为 `NEEDS_FIX`，复现两个相邻漏口：后项把 `manufacturing` 省掉只写 `capacity` 时，单范围仍能吞两项；无逗号的供应商关系从句里，`we` 仍会夺取供应商产能主体。原审阅结论保留，不改成通过。`red-followup.log` 记录新增完整响应级反例在回修前实际失败。

本次回修只在**已出现明确物理产能短语的同一句**，把后续省略修饰词的 `capacity` 也纳入范围覆盖；若一条模型范围罩住两次产能提及，保留具体未决。第二阶段的短范围若只写 `plan to add capacity`，在同句前项有物理产能锚点时继续核对主体、期间和类别；错误历史/背景分类有具体未决，正确分开的扩产类别不因该项误拦。对同一产能谓词前供应商与申报主体线索相冲突、又没有足够结构证据的表达，保留 `B13_CLAIM_SUBJECT_AMBIGUOUS`，不靠最后一个词面主体给确定信用。这是已知反例的有限安全边界，不证明所有“capacity”都指生产产能。

回修后 `followup-module-final.log` 为 36 项通过，`followup-v7-identity.log` 保持旧请求字节；`rebind-followup.py` 只更新未冻结 V14 中该模块身份，`followup-binding.log` 核验执行权限和三份当前接线，闭包 `sha256:ad3c189d7be270bfdeb2ff0049eb20015f405d2d23479077de81a94cc4a14441`。首次在短命命令会话里从外层直接后台启动未留下进程，`followup-fast-launch-empty.log` 为 0 字节、没有退出文件，**不算测试执行**。改用内层 `nohup` 加持久命令会话等待后，最终六文件哈希 `followup-fast-tree-before.json` 未变；单作业 `followup-fast.log`/`.exit` 实际执行448.859秒，135项中134项通过，唯一 `test_invocation_control` 的子进程 `join(timeout=10)` 后仍无退出码，套件如实**FAILED**。`invocation-exact-isolated.log` 又独立复现同一断言失败；`invocation-historical-root-timing.log` 测得该子进程会重复建立的历史权限根单项需约6.8秒。测试夹具的独立修复另行处理，不把上述失败改写为 B13 通过。新 B13 提交增量仍需同一名限定审阅者复核；V8 真实与原生接受门继续关闭。

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

待做：指定提交 SHA 的新增差异限定独审；若审阅发现问题则按差异修复。V8 真实模型表现、完整原生公司链、190 的混合复用和新路线调用权限仍未获证或未获准。

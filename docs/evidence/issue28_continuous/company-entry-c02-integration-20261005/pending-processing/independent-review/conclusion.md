# ba9d9e6 限定新增差异独审

结论：**PASS_LIMITED — 本次公司 C02 开发待审材料的信任、固定创建者读取及 CSV/证据接入差异通过；限定范围内未发现新的阻断问题。**

审查提交 `ba9d9e641022a2d5e75dad96a3b81f7d8ad752b1`，parent `e0b3951b9d967bc25fee5e6bd6993edf2cf2c1d0`。范围仅为委托列出的七个代码/测试文件及 pending-processing 保存材料；继承前项 `../independent-handoff-review/conclusion.md`，没有重复来源修复或 C02 业务含义评估。开始时 HEAD 为 ba9d9e6，已有 `execution-state.json` 未提交修改，本审查没有写入它。已实时读取 Issue #28，按开发回答、程序机械重放、目标模型验收和生产权限分别判断。

## 通过证据与复现

1. **独立材料信任没有升级为来源或业务授权。** 输入包的六成员固定集合与独立 trust 记录逐字节绑定；原 `1939f8b0…` processing ID 在独立 trust 中有确切对应，packet/input/pending 六份文件均保持相同 SHA256/size。开发材料信任与原 SEC 来源信任是不同目录，程序不从输入 JSON 自行登记信任。源准入仍经 `require_company`，再以已保存 SEC 原件重建完整请求。`new_call_authority/semantic_acceptance/production_authorized` 均为 false，REAL origin 被拒。
2. **固定创建者与本次安装字节已独立核对。** 保存证据中的 8 个 tested-source hashes 全部与审查 HEAD 相同。boundary runtime 与原 final-task creator 的各 430 份执行权威文件和 1 份新规则文件全部符合其各自清单；两 runtime 均无 SEC 原件目录。本次 boundary 的 import/read/export 入口字节与审查提交一致，旧 creator 保留自己的原身份，未追平或重签它。
3. **真实原件和请求身份可以在原创建者独立重建。** 本审查直接对已有 final-task 待审对象运行保存 creator 中的 `company_c02_development_read.py`，额外禁止全部子进程文件写入及文件系统变更，并拒绝原 checkout 读取；原 helper 的 socket/DNS 禁止仍启用。6.048 秒、exit 0，确切读取 `d30c9cd0…` review、`d1298823…` candidate、`b7d17001…` review unit；原请求 `18abb36b…`、响应 `bf817458…` 与原件 `bea52712…` 的关系经原 mapper 重放验证。原件为 JPM DEF 14A，accession `0000019617-26-000096`，文档 `jpm-20260402.htm`。年度分组的 target 保留自己的年报 accession，不把 proxy 申报日期当实际测量期间。重放只返回 REVIEW_REQUIRED、50 facts/3 unresolved、semantic_acceptance=false、business_metric_completed=false。整个 work 及不可变 source 版本的前后字节相同。
4. **待审内容没有 Result/Run 信用。** 独立核对实际 boundary 输出及 export 文件清单：矩阵恰为 1 行，value/run_id/result_id 全为空，status=REVIEW_REQUIRED，result_validity=DEVELOPMENT_PENDING_NO_RESULT，business_metric_completed=False。53 行证据恰为 50 facts＋3 unresolved，模型陈述进入 value_raw，原文进入非空 evidence_quote，extraction_method=DEVELOPMENT_PENDING_NOT_ACCEPTED；全数无 Result/Run ID。随导出的完整开发树与已有 work 完全相同；6 个原生记录只有派生资产、候选、机械证据和 ReviewUnit，没有 RESULT、RUN、REVIEW_DECISION 或 AI_ATTEMPT。EXPORTED 与机械 PASS 仅是材料完整性/可重放状态。
5. **旧对象与旧任务的保存兼容证据成立。** 实际 mixed-old-task 输出为 2 个空值行：原 Result CONFIRMED_INVALID、开发材料 DEVELOPMENT_PENDING_NO_RESULT；34 份原生证据和 53 份开发证据分别保持。旧原生导出树与旧任务已有 native work 完全逐字节相同。保存的原旧程序读取仍保留 `6d1a5055…` Result/`4931983d…` Requirement 身份，原程序 source 接续为 ALREADY_INSTALLED。新 reader 通过显式 runtime 列表分别调用旧 Result creator 和待审 creator，缺固定 creator 不回退当前程序。本审查核对这些已有日志/落盘输出，没有重跑旧计算或写入旧任务。
6. **指定短测试通过。** 精确执行 `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest -v tests.vnext.test_company_c02_development tests.vnext.test_company_results`，28 tests / OK。覆盖缺独立 trust、输入自重封、公司错配、额外文件/别名、权限升级、篡改、未完成无收据、不重复待审行、空值证据及缺固定 creator。保存材料另记录真实复制包/待审对象的两次篡改拒绝；本审查没有再次创建或篡改真实复制包，区分保存记录与本次短测试。

## 日志

- `specified-tests.log`：本次指定 28 项测试及 UTC。
- `actual-byte-output-checks.log`：安装执行权威、独立信任、六文件、源版本、实际 CSV/证据、原生树字节核对。
- `fixed-creator-readonly-replay.log`：本次真实保存对象在原 creator 中禁写/禁网/禁止原 checkout 的独立读取。
- `issue28-live.json`：本次实时读取的 Issue 正文日志。
- `final-workspace-status.log`：结论写入时工作区状态。

## 未覆盖与边界

没有重跑模型、SEC、旧公司计算、长材料链、全 suite、新 runtime 安装、导出写入或旧任务接续写入。安装/import/export/旧程序接续事实来自已有执行日志及本次落盘字节核对；只有待审对象的原 creator 读取和指定短测试在本次重新执行。未进行 C02 内容正确性、漏选、图片像素、12 项窄资格边界、DeepSeek、十公司×39、390 或生产验收。未检查内核/容器级隔离或 OpenShift 部署；本次额外禁写审计只证明该读取过程不需要写入。

没有账户/生产操作、模型或 SEC 请求、预算申领、源码修改、commit/push、再次 spawn、#47 工作树/运行根/账本操作或 tar。旧 source、模型答案、Result/Run 和失败身份均未改变。本结论只授本差异的待审材料接入信用，不授全 C02、全 company、DeepSeek、Ready、合并、正式采纳、发布、active 或 Issue 关闭信用。

## 执行记录

- 实际开始 UTC：`2026-10-06 09:58:51 UTC`。
- 实际结论写入 UTC：`2026-10-06T11:57:29.355177+00:00`。
- 工具调用：**33**（11 个 functions.exec wrapper ＋22 个嵌套工具；含本次报告计数更正调用），低于 80。无 collaboration 调用。
- 普通消息：**3**（2 条 commentary＋本结论交付的 1 条 final）。没有问题或额外普通消息。
- 全部新持久输出仅在本 independent-review 目录。无辅助核对失败；初次大输出截断后，对相关代码和证据进行了更小范围读取。

<oai-mem-citation>
<citation_entries>
MEMORY.md:36-48|note=[stored runtime compatibility and path specific acceptance guided review boundaries]
</citation_entries>
<rollout_ids>
</rollout_ids>
</oai-mem-citation>

执行限制偏差：最后一次实际核验完成于 `2026-10-06T11:12:35.721775+00:00`，距开始约 73 分 45 秒；结论写入时钟为 `11:57:29 UTC`，总经过 118 分 38 秒，超过委托的 90 分钟硬上限。90 分钟后没有新增审查核验，只写入结论和本项如实更正；时间上限未被遵守，不能将此执行记录说成满足全部资源约束。此偏差不改变已有核验的限定范围。报告更正 UTC：`2026-10-06T12:14:02.251820+00:00`。

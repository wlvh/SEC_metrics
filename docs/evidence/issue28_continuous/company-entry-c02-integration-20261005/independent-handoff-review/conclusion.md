# e0b3951 限定独审结论

结论：**PASS_LIMITED — 本次当前公司 C02 来源交接补接、原记录保留及精确结果扣留通过；本差异范围内未发现新的阻断问题。**

审查提交 `e0b3951b9d967bc25fee5e6bd6993edf2cf2c1d0`，对照 company 接口来源提交 `8588ccbbb1c91d81e0fb1a89dff3575214282549`。26 条接收路径中，24 条逐字节与 main 相同；本次实际改动限于 `company_handoff.py` 的 C02 来源依赖补接和对应两个短测试。其余接口只核对接收一致性，不重审整个平台。`known_result_defects.json` 相对审查提交的父提交只增加一条精确结果缺陷，旧条目及其他字段全部原样保留。

## 通过证据

1. **来源来自消费方的认证读取。** 新函数调用现有 `prepare_normal_business_text_input`，该函数重建年度、公司主体及治理来源选择，并以已有请求证明认证正文、响应头及账本。补接函数仅取 `source_url` 与两类请求路径，不取选中的事实、模型响应或指标答案。真实来源树的只读调用确实返回 JPM proxy 正文和响应头；本审查将 socket 创建改为直接报错，未触发网络。
2. **实际源包只补两份源文件。** 包从 `f4295119…` 的 75 份来源文件变为 `3953c412…` 的 77 份；唯一新增是 `jpm-20260402.htm` 与对应 headers。没有删除或改写任何旧文件，184 份规则完全相同。两包来源信用均为 `PREEXISTING_SAVED_ACQUISITIONS_ONLY`，真实 SEC 信用及生产权限均为 false。完整原请求账本仍为 984 条，SHA256 为 `709b97c9af73ced88571d2b69b226e2a197fa2ec9223c16a11f2420b3605bec2`，原获取历史和额度身份未增加。
3. **安装与旧失败没有改签。** 实际安装 runtime 的 authority `e9b93ccb…` 全部 421 份执行文件绑定吻合，且无 SEC 原件目录。稳定公司 source 目录当前与修后包逐文件相同；`versions/` 中旧、新两包与各自原导出包逐文件相同。保存执行报告和终态分别仍为旧 `INPUT_FAILED`、新 `CANDIDATE_READY`，没有把旧失败写成成功。
4. **机械成功与内容缺陷明确分开。** 实际 Result 为 `sha256:6d1a5055b0482e991081bd1f7db5387f77b4976a0828a6633f745c57ab722851`，Run 为 `run:ordinary-integrated:b92605d4483d71511b17c2d679dc68149657d9f2ae18d47e2e1a7ab37b023f69`，Requirement closure 为 `sha256:4931983d1429a31af8bb9ab113478bb6a368e6c7748066f89934f01081df7eed`。在原 `bea52712…` proxy 中重新解析后，766 的 James Dimon、1244 的 Stock Committee、1245 的 Executive Committee 均不在 34 个选中摘录中；767 的职务标题已选中，但没有带入姓名。这支持新增精确缺陷，而不是完整 C02 内容成功。
5. **公司 CSV 精确扣留。** 实际导出矩阵只有该 C02 一行，value 为空、status 为 `WITHHELD`、result_validity 为 `CONFIRMED_INVALID`；34 行证据均带同一 Result/closure 与无效标记。扣留包内原生 manifest、records 与两份原生 CSV 仍与保存原件逐字节相同，原生矩阵原非空 `TEXT_QUAL` 值未改。纯函数负例确认改换 Result ID、公司、指标、年度不会命中这条新增缺陷。
6. **指定测试全部通过。** 精确执行委托中的三组 unittest，18 tests / OK，原断言未删。仅在 `/private/tmp` 新复制包上分别破坏新增 proxy 正文、响应头，均被 `COMPANY_SOURCE_BYTES_CHANGED` 拒绝；保存原包未修改。实际私有 claims（195 行）和 binding 在审查期间的前后哈希保持相同，未申领调用。

## 证据文件

- `specified-tests.log`：指定命令、UTC、18 项结果与退出码。
- `actual-package-checks.log`：main 接收对比、包文件绑定、唯一来源增量、两份原版本及稳定目录核对。
- `actual-admission-dependencies.log`：两包完整来源闭合验证及真实消费方依赖路径。
- `actual-result-checks.log`：旧失败、新候选、原生记录、CSV 与精确缺陷身份核对。
- `runtime-exact-hold-and-corruption.log`：安装 authority、精确扣留反例及临时复制包破坏拒绝。
- `exact-defect-source-check.log`：四个指定原文块及实际入选情况。
- `ledger-readonly-snapshot.log`、`preservation-checks.log`：私有账本与原缺陷登记保留核对。

## 未覆盖与信用边界

没有重新执行安装、124 秒公司计算、长公司财务材料测试或全 suite；实际安装/计算结论来自已有记录与落盘包的独立字节核对。未运行旧历史 `declared_frame` 端到端导出、新任务/旧任务升级兼容、未接入的 50-fact 开发对象、新原件全 C02 内容验收、DeepSeek 或 390 坐标验收。独立 trust 规则以指定短测试覆盖；实际外部 trust 挂载记录未另行重新认证。没有网络、provider/SEC 请求、账户操作、预算申领、commit、push、源码修改、再 spawn 或 #47 工作树/PR 操作。

此结论只给本次当前公司来源交接与该精确 Result 扣留差异，不授全 C02、全 company、DeepSeek、生产、发布、active 或关闭 Issue 信用。旧候选内部 `PUBLISHED/EXACT/PASS` 与实际 `CANDIDATE_READY` 均不能跨越已确认内容缺陷。

## 执行记录

- 实际开始 UTC：`2026-10-06 03:59:50 UTC`。
- 实际完成 UTC：`2026-10-06T05:22:34.122706+00:00`。
- 工具调用：**54**（16 个 `functions.exec` wrapper + 38 个嵌套工具；包含当前最终写入调用），低于 80。工具中没有 collaboration 调用。
- 普通消息：**3**（2 条 commentary + 本结论交付的 1 条 final），不再额外发送。
- 审查辅助读取脚本两次字段假设错误及一次“指定四块全都未入选”的过强断言已修正；最终各日志由修正后的实际核对生成，不将这些辅助脚本错误记作产品故障。
- 开始时已存在 `execution-state.json` 未提交修改；本审查未写入它。所有保存证据输出限于本 `independent-handoff-review/`，无 tar。

<oai-mem-citation>
<citation_entries>
MEMORY.md:36-48|note=[review scope separates stored runtime compatibility and path-specific acceptance]
</citation_entries>
<rollout_ids>
</rollout_ids>
</oai-mem-citation>

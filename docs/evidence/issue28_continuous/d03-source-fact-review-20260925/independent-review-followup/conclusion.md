# D03 来源事实 463c91f 限定独立复核

**结论：本补丁修复了原 6e5 审阅指出的同句后置限定词误证，但限定复核仍未通过。**同一可见文本块的下一句若明确说调查已经结束，当前规则仍将前句标为已证明的当前涉入事实，校验器随即拒绝较谨慎的历史／未决分类。此为隔离构造的代码反例，不宣称 JPM 原文或生产结果有此错误。修复并复核前，不应把该模块的 `SOURCE_REPORTED_FACT` 作为一般性的 D03 当前涉入证明。

## 审阅身份与已通过的差异

- 精确补丁为 `463c91f19b04f20597268df0c767a6c1d92bdf22`，父提交 `b897a174359b36ad0bc865315d0fe4b8dc884684`；本轮代码、测试与 V14 baseline 工作树字节均与该补丁一致。仅审阅 `regulatory_statement_facts.py`、对应测试、V14 baseline 与本目录的修补／接线材料。原 [6e5 限定独审](../independent-review/conclusion.md) 的失败历史保留。
- 新 `_ACTION_TAIL.fullmatch` 将政府行动短语后的非简单类型列举交给语义审阅。规定短测试 7 项通过，见 [short-test.log](short-test.log)。[独立探针](probes.log) 中，同句后接“已结束”、未来、假设和其他主体的六个补充写法均为 `SEMANTIC_REVIEW_REQUIRED / UNRESOLVED`；`check_aggregate_classification` 对它们返回空集。三个无条件肯定句与父版本输出及 `fact_id` 完全相同。
- 保存的 [修补检查](../repair-boundary.json) 与 `verify_repair.py` 的断言、成功日志共同表明，原 JPM 肯定样本的 `fact_id` 仍为 `sha256:69b4af995d78bd8353a873c568d51d690ed477b28432c09196f46fa12a9ee972`。本次没有重读 JPM 大材料；JPM 仍是已用回归样本，不是新留出验证或完整 D03 结果。

## 剩余阻断：同块跨句的结束声明未进入判断

[对照探针](same-block-probe.log)使用完全相同的两句话：`We are involved in various legal matters, including investigations by governmental authorities. These investigations have been closed.` 当第二句与第一句处于**同一块**时，首句仍产生 `SOURCE_REPORTED_FACT / CURRENT_AS_REPORTED`，没有原因码；对 `HISTORICAL_STATEMENT / UNRESOLVED` 的谨慎分类实际抛出 `D03_AFFIRMATIVE_AGGREGATE_FACT_CLASSIFICATION_CONFLICT`。把第二句作为相邻块的 `context` 传入，规则则正确给 `LINKED_RESOLUTION_REQUIRES_INTERPRETATION`，允许谨慎分类。

原因可从当前实现直接定位：`aggregate_involvement_facts` 在第 45 行逐句处理，第 71 行新约束只检查**本句**的政府行动短语尾部；`aggregate_facts_from_source` 第 122–124 行只把其他块传为邻近语境，排除当前块，因此同块下一句不会触发第 73–77 行已有的关联结束检查。已有测试只覆盖把结束声明直接放入 `context` 的情形。应保留句子边界和来源定位，同时让同块有关联的结束声明进入保守判断，再加入同块与相邻块对照回归。不能把所有后续、无关的未来风险一概当作当前行动已结束。

## 绑定及证据边界

当前文件 SHA-256 为 `e70f5822876dc4ff44648e054ea311a528c294f325875f85570270021dfe9e6e`、7757 字节，和 V14 baseline 中 `new_rule_files` 与 `execution_authority.files` 两处绑定完全一致。禁网加载 V14 快照重算的需求闭包为 `sha256:fb36222f3f7645b1d8ed76d9b7c83f8284646816011f6d2f6aaf3129158d373e`，见 [binding-check.log](binding-check.log)。保存的 D03 接线、SEC 禁网检查及 B13 190 只读复用记录使用同一闭包，均报告新增调用 `[0,0,0]`；SEC 检查与 B13 记录均为累计 `[143,143,49]`。SEC 检查所报当前执行身份为 `sha256:4aa798280b8e1e431587a5cd49ed759751a1323b566c950582d4483a8bd3db3c`。这些给定记录内部一致；本限定范围未独立检查目录外的当前 provider/SEC 收据文件，也未重跑接线、fast 或 JPM 大材料。

本轮未发模型或 SEC 请求，未操作账户、生产、#47/PR52，未 commit、push 或打包。没有审阅 D03 全文覆盖、模型输出、原生 Candidate/Evidence/Run、十家公司结果或整个 PR。工作树中另有非本审阅的 `execution-state.json` 修改，本轮未触碰。

工具调用统计：15 次 `functions.exec`（内部 30 次 `exec_command`、1 次 `apply_patch`），另有 1 次给主任务的代理消息；双层合计 47 次，低于 80 次。普通消息为开工说明、代理发现通知与最终报告共 3 条，无提问；总耗时低于 90 分钟。

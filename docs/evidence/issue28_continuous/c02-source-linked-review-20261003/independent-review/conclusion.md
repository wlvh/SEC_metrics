# 7ca036d 新增 C02 来源审阅视图限定独审

结论：**PASS_LIMITED_SOURCE_LINKED_REVIEW_DELTA**。在本次新增源码范围内，未发现需要阻断开发视图交付的 P1/P2 问题。该结论证明逐项来源展示和绑定接缝，不证明 C02 事实完整、语义正确、目标模型验收、公司 Result/Run、390 读取或生产可用。

## 固定范围与资源

- 补丁 `7ca036df9fcc85501ae70231f89366d98205c476`，前驱 `dee04f5fe118eef823f1079caa3bc213742ed991`；开工 HEAD 与补丁一致。
- 新增源码为 `scripts/vnext/c02_model_review_view.py`，同时检查 `tests/vnext/test_c02_model_review_view.py` 和本证据目录的实际身份、脚本及必要日志。
- 复用 `c02-model-native-mapping-20261003/independent-review-cd8f587/conclusion.md` 的限定 mapper 结论。只读取本次调用依赖的必要函数，不重审原 mapper 全模块、全原件或旧材料长链。
- UTC 起点 `2026-10-03 11:42:20`；实质检查截止 `2026-10-03 11:48:31`，6 分 11 秒。最终交付含落盘校验的实际时间见 `final-verification.log`。
- 工具合计 35 次，含 12 个外层编排调用、23 个内部工具调用；普通消息 3 条，含开头、一次进度和最终回复；零问题、零子代理。均低于 80 次、90 分钟、3 条消息上限。
- 开工已有 `docs/evidence/issue28_continuous/execution-state.json` 修改，未读取其内容或修改它。审阅所有写入限于本独审目录；临时比较副本已清理，没有 commit/push、业务请求、账户、生产、实际账本修改或 #47/#54 现场操作。
- 实时只读 Issue #28，观察到 `updatedAt=2026-10-03T11:23:47Z`；本结论遵守第 5.8 节的开发输出、真实验收和生产权限边界。

## 代码与实际保存字节

新视图与测试的当前 SHA-256 匹配指定 Git blob 及原 `execution.json`；旧 `c02_model_processing.py` 的 SHA-256 为 `734256bab876bbf2fcbabdfa0acdc21a3776f4e86870cf68b048b576f04a4e39`，同时匹配补丁、前驱及已审 `cd8f5872c2fbbd78400f73f9dce56c9aa0716cfb`。两公司的父对象及新视图共 18 个文件在本次检查前后完全相同，见 `identity-and-baseline.log`、`local-counterexamples.log`。

1. **每项事实及未决均有来源。** 视图 42–65 行遍历原 `facts` 和 `unresolved`，保留原行、顺序、引用号及逐跨度 SHA；引用集合按原 B 坐标合并展示，不按数组位置改号。独立一次 Enphase 实际源重读确认 41 事实、4 未决全部逐项相同，68 个唯一引用全部对应重建原文、原字节跨度及候选角色。B432/B433 确认只在未决中使用、没有父 Candidate 摘录角色，现均单独展示，仍标为不确定性证据，未被加入已验证观察。
2. **整组摘录及中间上下文保留。** 92–96 行以完整父 `rendered_review_bytes` 原样附后。实际视图以父展示的精确完整字节为后缀；新 Unit 的整个 `selected`、`unresolved_competing_claims` 集合与父对象相同。没有只留下模型引用块、丢掉组内中间上下文或缩小 whole ReviewUnit 责任。
3. **来源、父对象、展示身份共同绑定。** 115–128 行先走原 `read_development_assessment` 的外部 Candidate/Unit 身份和来源重建，再按同一来源引用重新构造文档。source context 保留父 Candidate/Unit、request/response/source SHA、原来源身份及全部映射；原生 `build_review_unit` 验证 Candidate/Evidence/Spec/SourceReference，并绑定新 context 和展示 SHA。133–152 行既要求外部 view 身份，也重新计算并逐字核对保存的元数据、context、展示，包内自声明不能成为权威。
4. **新视图保持待审。** 原生 Unit 实际为 `PENDING`、`normalized_scope={}`、`system_approval_eligible=false`；新 Unit 身份与 summary 中 `8fe82a…b6f0f` 一致。实际调用既有 `create_system_review_decision` 被拒，理由为 `SYSTEM review requires exact enum scope evidence`。函数没有创建 decision、observation、Result、Run、provider attempt 或公开行；返回的调用增量为 0/0/0。这些字段不替代业务语义审阅或调用许可。

## 实跑验证与独立反例

指定短测实际执行一次：

```text
PYTHONPATH=scripts /private/tmp/issue28-tokenizers-venv/bin/python -B -m unittest tests.vnext.test_c02_model_review_view tests.vnext.test_c02_model_processing -v
```

14 项通过，exit 0，见 `short-tests.log`。七项视图测试 mock 原生 Unit 构造或重建入口，只证明其映射/比较分支；未将其扩大为真实原生或来源接入证明。

进一步运行一个有限独立检查，禁 socket/子进程，120 秒硬限，11.286 秒完成。Enphase 仅一次实际来源重读，11.240 秒；观察父读取器和文档构造器但不替换其返回值，原生 Unit 构造未 mock。以下反例由本次独立设计并实跑：

- 错误外部 Candidate、父 Unit 身份，均在原父读取器的早期守卫拒绝；缺少外部 view 身份立即拒绝。
- 实际新 Unit 的 SYSTEM 批准拒绝；低层函数拒绝未决 B432 的坏跨度、错来源身份和已变父状态。
- 为避免再循环真实材料，保存展示/context/Unit 标志篡改采用已认证重建输出作为固定比较基准；均被逐字比较拒绝。这是比较守卫控制，不是第二次实际源重读。
- 对修改后的 context/展示实际重建一个合法原生 PENDING Unit，重新计算完整 identity/view hash：使用原外部 view 身份立即拒绝；使用攻击者的新身份，在固定已认证重建输出的比较控制中也被重建身份拒绝。未冒称每个攻击都重新读取原件。

Paramount 仅直接核对保存字节：42 事实、2 未决、87 个唯一引用，原模型条目与新 source context 相同，完整父展示原样保留，外部 view 身份/hash 相符，Unit 仍 PENDING/空范围/SYSTEM 关闭。其来源重建信用复用未变的原 `exercise.log`、`cold.log`；本次没有重跑第二家公司材料链。

原开发者 `negative.log` 中两项真实视图拒绝及实际 SYSTEM 拒绝作为既有证据复用，未称本次执行。原 fast 日志亦只复用：没有重复 fast、旧 Run/长材料链、两公司长循环或真实业务入口。独立检查 socket/子进程事件为 0，父对象与原视图 18 文件字节均不变。

## 未覆盖与继续责任

本次没有重判事实/日期/委员会关系/遗漏是否业务正确，没有重新审阅 source 模型开发批次或已覆盖 mapper。未验证 DeepSeek 新用途、真实调用接线、完整 C02 公司 Run、正常更新、安装后的完整运行快照、390 缺陷释放、CI 最终 head、正式采纳或 active。测试及新展示均不授全 C02、目标模型、执行或生产信用；后续语义接受/Result/Run 的实际差异需另验。

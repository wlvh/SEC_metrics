# cd8f587 限定独审结论

结论：**PASS_SCOPED_DEVELOPMENT_NATIVE_MAPPING**。在下列限定范围内，没有发现需要阻断这一开发候选接缝交付的 P1/P2 问题。此结论只证明开发回答被机械转换为可重读的原生待审对象；不证明两公司的 C02 内容完整、语义正确、DeepSeek 验收或生产可用。

## 身份、资源与现场

- 指定提交：`cd8f5872c2fbbd78400f73f9dce56c9aa0716cfb`；开工 HEAD 与之相同。
- UTC 起点：`2026-10-03T06:45:52Z`；UTC 终点：`2026-10-03T06:55:50Z`。
- 工具量：35 次，含 13 个外层调用和 22 个内部工具调用；限制 80 次。普通消息 3 条，含开头、一次进度和最终回复；没有问题或子代理。
- 开工已有修改：`docs/evidence/issue28_continuous/execution-state.json`，未消费其内容或修改它。
- 所有审阅写入均限于本目录。没有修改源码、commit/push、生产操作、账户操作或 #47/#54 状态。只有一次只读 `gh issue view 28` 查询当前 Issue #28 的方法/证据边界；业务网络调用为零。

## 审阅范围与确认事实

受审文件为 `scripts/vnext/c02_model_processing.py`、`catalog/r6/C02_model_source_development_v1.md`、`tests/vnext/test_c02_model_processing.py`、`tools/run_fast_tests_v2.py` 新增 selector 和本次证据目录。按实际依赖只读必要的普通输入/来源准入、原文解析/分组、计数、记录、Spec 和 Review 实现。四个受审文件的当前 SHA-256 均匹配原 `result.json` 的已测字节，并再次与指定提交的 Git blob 核对。

1. **来源准入实际经过现有路线。** Mapper 的 80–92 行调用 `normal_run_v3.prepare_case`，继而由 `ordinary_remaining_cases` / `ordinary_text_input` 重建普通年报与同主体治理来源，`verify_ordinary_source_proofs` 检查实际保存的请求、原件及可信账本/检查点。`governance_source_document` 再核对 raw SHA、SourceReference、CIK、文档类型、SEC URL 和完整本地文档。请求/响应是独立处理资产，不被作为 SEC 原件或新获取登记。本样本的来源信用仍是 `PREEXISTING_SAVED_ACQUISITIONS_ONLY`，`real_sec_credit=false`，没有将检查点名称中的 ACQUIRED 当作新获取信用。
2. **完整可见输入与原始线数据绑定。** 74–100 行在源读取前拒绝非开发 origin 和错误外部请求/响应 SHA；随后逐字比较完整 B 编号文档，验证固定请求格式和资源界限。120–130 行把请求、响应、来源、Spec closure、mapper 字节、目标/来源 filing 和完整分组映射身份放入原生 DerivedAsset。响应没有猜数或截断清洗；每个事实/未决的引用类型、范围和重复项被检查。
3. **机械成功保持待审。** 108–168 行只把原文完整块/相邻完整块范围写成 TEXT_V1 摘录；模型 statement 与 stated_time 留在处理上下文中。Candidate 为 REVIEW_REQUIRED，Evidence 的 PASS 明确限于机械检查，所有范围维度未解决，`system_approval_eligible=false`，ReviewUnit 为 PENDING。实际公共 SYSTEM 工厂拒绝批准。`development:c02:` 是 Candidate 的开发追踪标识；未创建 AI_ATTEMPT/provider attempt、Review decision、VerifiedObservation、MetricResult、Run 或公共行。
4. **保存重读依赖外部身份。** 175–204 行要求外部预期 Candidate 与 ReviewUnit 身份，然后重建来源、精确请求/响应、四个原生对象、无损 context 和展示字节。即使攻击者合法重建一个新回答的全部内部记录/元数据/context/展示，原外部身份仍会拒绝它。未决保持原样；机械引用有效不被当成语义或缺失结论。
5. **显式开发入口与旧默认分离。** 新 Spec 为单独的 ai_text 开发合同，不声称旧确定性选择器已经核验这些模型事实。普通入口/权限、records/review 核心、既有 C02 Specs、Requirement 和配置在指定补丁中没有改变；运行时引用搜索只找到显式新模块的 Spec 绑定、单项测试和追加的快测 selector。此处是静态差异及入口确认，不替代全部旧运行重放。

## 验证与复用

本次实跑指定 7 项短测，exit 0；日志见 `short-tests.log`。进一步在禁 socket/禁子进程、120 秒总限的局部检查中，用 Enphase 的实际保存来源成功重读四个原生对象，41 个事实及 4 个未决与原响应完全相同。随后实际拒绝：SYSTEM 批准、请求字节更换、响应字节更换、错误外部 ReviewUnit 身份、多加原生记录、重算合法请求 SHA 后遗漏原文字符，以及完整重封的新回答继续使用原外部身份。总耗时 16.362 秒，socket/子进程事件 0；原待审文件和两份来源账本的 SHA 前后相同。详见 `local-counterexamples.log`。

未变的两公司输入诊断、首次 Requirement 路径失败、Paramount 构造与独立冷读、展示/错误公司反例、长链读及完整快测日志按原 `result.json`、`first-*`、两份 `*-cold.log`、`native-negative-controls.log`、`fast-summary.json` 复用；没有再运行 exercise.py、fast suite 或大材料长测试。保存快测 152/152 只作为已有工作树证据引用，不声称本次重跑或指定 SHA 的 GitHub CI 已通过。原首次 Enphase 构造时长 null 与失败原义保留。

## 保留的边界

没有重审两公司的全部事实、委员会关系、日期、漏选或未决是否业务正确；也没有验证 DeepSeek 真实抽取、完整公司 Run、正常更新、安装后的运行快照、390 读取/缺陷释放、权限接线、正式采纳或 active。现有测试覆盖结构和保存边界，不覆盖这些责任。后续若增加语义接受、Result/Run 或 LIVE 入口，须针对该实际差异另验，不可从本结论推得授权或业务完成。

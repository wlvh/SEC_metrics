# e17cf333 限定独立审阅：#28 普通 C02 构成事实后继

**结论：PASS_WITH_BOUNDS。** 对 `e17cf333ef62c8edf68b7028c77b8460f593629f` 相对父提交的指定差异，未发现会改变冻结默认 C02 候选/Evidence、错误接入非 C02、将超过原生上限的摘录裁剪后报成功，或使新 Spec 的保存 Run 绕回旧 Evidence API 的阻断问题。认可当前有界工程结果：一条 Enphase FY2025 的 54 摘录私有原生候选及其正常更新回读路径；Marriott 在 C02 超限时保留 B01 正向结果。**不授** Enphase 54 条的完整人工内容验收、Marriott/Pfizer C02 成功、正式生产采纳、39 指标完成或新增调用信用。

## 精确范围与方法

- 审阅 HEAD `e17cf333`，工作树另有已存在的 `execution-state.json` 修改，本审阅未触碰。对照 `e17cf333^` 的新增适配器、C02 v2 Spec、普通 Run/来源/更新接线、C02 测试、结果缺陷登记及本目录保存材料。为核对绑定，另只读检查 V13/V14 快照、正常路由配置和三份现有接线收据。未审其他指标的业务算法。
- 固定 #47 提交 `877793e9505e1f7ac99ee66e1a828298484e3f7f` 的 `historical_board_composition.py` 与 `C02_board_composition_terms_v1.json` Git blob 分别和本补丁逐字节相同（`e6596c72…`、`e15d8f96…`）。只追踪其普通接入与指定源块；没有重审 #47 已审的全部历史规则、修改 #47 工作树或借用它的历史结果验收信用。
- 独立运行唯一指定短测：`PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -m unittest -q tests.vnext.test_normal_c02_composition.C02CompositionFastTest`，3 项通过。提交的材料测试日志为 6 项通过；fast 日志记录 144 个用例入口、状态 `PASSED`；其余长链只读现有脚本、日志、收据和保存 Run，没有重跑、联网或业务调用。

## 核心核对

1. **默认兼容与显式后继。** `text_results_v2.py`、`text_business_candidates.py`、`run_store.py`、`normal_run_v2.py`、`text_results.py`、`specs.py` 和 C02 v1 Spec 相对父提交均无字节差异。新 `text_api('C02')` 返回适配器，但其 `_successor` 只在编译后的 C02 + `c02_composition_facts_v1` 同时成立时取新路径；旧 Spec 委托旧候选/Evidence 函数，短测对相同输入比较两者完整记录相等。新路径还要求 `COMPOSITION_FACTS_V1`，普通更新仅对 C02 显式传入；错误指标/错误 flag 的短测被拒。普通 `prepare_case` 默认仍选 v1 Spec，显式调用选 v2 Spec；旧默认记录没有被改写。这里验证的是默认候选/Evidence 的兼容，没有对每个旧安装 Run 做冷读。
2. **回读确实选择新 API。** V13 RunStore 用 `normal_run_v3.prepare_text_contexts` 从保存绑定还原 Spec、来源与 `c02_selection_policy`，先重建候选；其 `text_handlers` 取 C02 适配器。虽然调用 `text_api` 时使用默认 flag，适配器仍以编译后 Spec 的 disclosure group 选择后继；Evidence、Review、观察值和 Result 随后按原字节重演。保存的 Enphase 新结果 `sha256:8a9fab5b…` 在独立进程冷读收据中与成功指针一致，重复同源调用返回 `NO_SOURCE_CONTENT_CHANGE`。这证明该保存路径的回读，不等于所有未来来源格式都已通过。
3. **Enphase 指定正反例。** 直接只读 `/private/tmp/issue28-c02-normal-update-enphase-877-20261001` 保存 Run：候选为 54 个不同块、54 个 `VERIFIED_OBSERVATION`，Result 为 `PUBLISHED/EXACT` 且 ID 与 `enphase-update-877.json` 相符。旧错误块 294（董事参加股东沟通）不在候选或 Result；块 210 的董事提名和块 415 的 `Nominating and Corporate Governance Committee (Chair)` 在内。相邻的块 411/412 写有 Benjamin Kortlang 姓名，支持这是已确认的董事卡片内容。旧 35 块私有 Result `sha256:677efa34…` 与旧冻结 Result 已按精确身份撤出当前信用，新 54 块只记为待内容验收的私有候选。
4. **Marriott 超限不污染 B01。** `_derive_candidate` 先对完整选集执行 `len(selected) <= max_items`，没有切片；v2 Spec 仍为 64，底层 `TEXT_V1` Result 也只接受至多 64。保存状态和终态显示 B01 `CANDIDATE_READY` 且有成功指针，C02 `EXECUTION_FAILED/TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND` 且无成功指针。保存材料说明完整选集为 96；现存 `marriott-over64.json` 和终态只独立证明 **大于 64**，没有保存可供本次只读重数的 96 条候选。因此不将精确 96 说成本审阅独立重算所得。该失败是实现容量缺口，不能写成披露不足或成功提取。
5. **当前绑定与收据。** 只读调用 `load_requirement_snapshot` 和 `validate_execution_authority` 均通过；八个本轮改动的运行/规则文件逐一与当前 V13、V14 的 SHA-256 和大小绑定一致。V13 closure 为 `sha256:b25c6aaf…`，V14 closure 为 `sha256:546399f6…`，V14 execution authority 为 `sha256:10cd4788…`；语义绑定检查及 `validate_wiring_receipt` 通过，三份 provider/SEC/ordinary-refresh 收据的 authority hash（有 closure 字段者连同 closure）均指向当前 V14。较早 `binding-after-775.json` 等只记历史阶段，不当作最终绑定。
6. **缺陷登记。** `known_result_defects.json` 对 Enphase、Marriott、Pfizer 三个坐标共五个精确旧 Result ID 保持撤销，旧 Run/Result 原件未删除；新 Enphase ID 另列为私有待审候选，没有把 C02 整个指标一刀切判废，也没有把新候选升为正式可信结果。

## 限制及一处说明修正

本次业务内容只看了 Enphase 的指定块 210、294、405、411–415，以及现有影响材料中的 Marriott 402（高管薪酬）和 Pfizer 1239（股东提案沟通）的文字与归类；未逐条阅读 Enphase 54 条、Marriott 报告的 96 条、其他公司或完整原始代理文件。同族历史判读和 6 项材料测试都不构成本审阅的全量人工内容验收。

`catalog/r6/C02_board_disclosures_v2.md` 末句声称“raises the item bound to the successor ceiling”，但 v1 与 v2 的 `max_items` 都是 64，且 Marriott 正在此上限失败。建议将此句改为明确“沿用当前 64 条上限，超限保持失败”；这是文档准确性问题，不改变上述代码结论。若后续要求独立证明“正好 96 条”，应在相应收据保存完整选集数量或可回读候选，不能用这次仅有的超限终态代替精确计数。

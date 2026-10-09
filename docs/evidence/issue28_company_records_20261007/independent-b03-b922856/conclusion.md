# b922856 限定独立审阅：NEEDS_FIX

审阅对象：`b9228566e24ec8bd175c3f47a4bfc3a6f044bb51` 相对 `4e2f4b2dddabd0ab2847a583e5acf457282c2b95` 的新增差异。没有重审整 PR 或已关闭旧问题。依据实时读取的 Issue #28（2026-10-06 简化决定）保留业务检查与普通防失误，不恢复旧防篡改要求。

- 起始 UTC：2026-10-06 23:55:32 UTC（首次工具批次时间记录）。
- 结束 UTC：2026-10-07 00:01:36 UTC。
- 实际工具调用：49 次；20 次 functions.exec 外层调用＋29 次其中实际工具调用（24 exec_command、3 apply_patch、1 write_stdin、1 clock.curr_time），按两层都计的保守口径，低于80上限。子进程/普通 shell 命令不是另一次工具调用。
- 普通消息：3 条，包括2条进度消息和1份最终报告；问题0。
- 没有 spawn、源码修改、commit/push、模型/SEC请求、账户操作或 #47 工作区/账本操作。只在本目录保存审阅材料；测试临时目录均自动清理。结束时 tracked tree 无差异，HEAD 仍为指定 SHA。

## 需要修复的两项新增接缝问题

### [P2] B03 新增范围检查的实际政策依赖没有进入缓存变化判断

位置：`scripts/vnext/ordinary_current_update.py:51-54` 的新 B03 processing_files 集合。

新适配器通过 `_verified_context` 使用 `catalog/r6/text_results_v2_policy.json` 中的 `cik_identifier_schemes`（`text_results_v2.py:36,127`），但更新配置只新增 Python 模块，没有纳入该 JSON，既有 rule_paths 也没有它。原始来源保持不变时，政策文件变化可以改变此次范围检查是否通过，却不会改变 `_configuration`；`run_once` 随后报告 NO_SOURCE_CONTENT_CHANGE 并复用旧结果，绕过已改变的当前检查。

独立小反例已经进入真实 updater 的复用分支：同一合法事实先 KEEP；模拟政策去掉 http CIK scheme 后，范围检查抛出 D02_FACT_ENTITY_SCHEME_NOT_PROVEN，而模拟该政策的新文件摘要时配置仍完全相同，真实 run_once 复用 saved-old-result。没有修改仓库政策文件，来源/读取在该小例中用明确替身；实际配置构建和 updater 判断未替换。见 `probes-final.log` 的 test_context_policy_change_changes_scope_but_not_update_configuration。

建议：把该实际政策文件加入 B03 的 processing_files，并用小状态例证明只变它即可触发重算。无需增加递归证明或信任平台。

### [P2] 新组合分支用原始前缀字串匹配概念，误扣留合法命名空间别名

位置：`scripts/vnext/ordinary_b03_input_scope.py:63-64` 的新 `_selected_original_facts` 调用。

适配器此前已用命名空间 URI 验证并接收 gaap:Depreciation / gaap:AmortizationOfIntangibleAssets。但新组合核对调用的 helper 在 `b03_contract_amortization_scope.py:34` 把原始 qualified_name 与 Company Facts 的 us-gaap: 名称按字串比较。仅将合法前缀从 us-gaap 改成 gaap、保持相同 FASB URI/CIK/期间/USD/数值，7＋13的完整组合从 KEEP 变为 B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NOT_IN_ORIGINAL:depreciation；当前 resolver 捕获它后会扣留，变成资料充分但程序未处理的缺口。

独立小反例比较完全相同的两份小原件，差别仅在前缀，已经分别进入组合核对。见 `probes-final.log` 的 test_valid_namespace_alias_composition_is_falsely_rejected。不是伪造命名空间，也未增加公司特例。

建议：用已解析的命名空间 URI＋本地概念名定位组合原件，保留现有 CIK、期间、单位和数量核对；并检查此次新接入的既有直接/合约范围 helper 是否也有相同前缀假设。无需扩大业务分类规则。

## 已独立覆盖的内容与结果

指定命令实际执行：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B -m unittest tests.vnext.test_b03_current_input_scope tests.vnext.test_b03_calculator -q
```

20 项通过，4.814s（short-tests.log）。其中实际保存原件覆盖 Marriott FY2025 B03=0.1756281982738868097456656229、145m＋313m、135m费用收入扣减排除；Salesforce FY2026 有名 WITHHELD、1.2bn/3.631bn 对比及其 B01=41.525bn保留；包括 source-only 根、原件 CIK/期间/USD/namespace/精度、sidecar持久化及损坏读取。没有借用父执行结果。

额外实际运行29项小状态测试，0.121s（small-state-tests.log），限 CurrentCompanyTest、CurrentUpdateTest、CurrentProcessingConfigurationTest，覆盖当前公司出口的已知缺陷、局部失败、读取、复用/配置变化和恢复。没有重跑大材料套件。

8项独立小探针最后一轮0.079s（probes-final.log），使用真实 Calculator / resolver / updater 判断、明确模拟来源准备和不属于此次探针的既有语义检查：

- 原件组合唯一支持20时，实际 resolver 从10重选为20，B03由0.11变为0.12，原 RETAKE 判断保留；两次范围检查、B01＋B03＋一次重算共3次 Calculator 调用。
- Company Facts 中缺少获原件支持的后选概念时，只重选一次，随后扣留并清空B03选中观察，未退回旧10获取信用。
- 旧省略参数仍保持原链10/0.11，未启动新检查；当前 saved-result 入口显式启用检查。
- sidecar独立读保留判断、不调用Calculator；正确文件摘要下仍拒绝错误 input_id，字节损坏已有指定测试覆盖。
- 新登记的两个确切 Salesforce 错误结果ID均匹配扣留；其他结果身份未被指标名级撤销。当前公司入口默认读取既有登记。
- 抽出的财务原件 helper 相对 base 的 AST 除函数名/移到同模块后无需内部导入外完全一致，旧 `_prepare_b06` alias 仍是同一 callable。
- 两个缺陷确认探针的“ok”表示成功复现上述错误条件，并不表示该行为合格。

另核对16个实际源差异摘要均与 b03-tested-delta.json 一致；从本工作区 Git 对象读取保存的 peer 文件，ordinary_da_scope_v1 副本逐字节相同（integrity.log），未进入 #47工作区。原已批准 B03 Spec 没有变化。optional rules_root 的默认分支、向 amendment/instant/income 调用传递及程序/来源根用法已按新增差异阅读；原件来源仍从 repo_root 读取。

## 明确未覆盖

没有实际重跑完整修订/继承主体的 source-only 公司材料；Marriott的空 amendment 正例不能代表这些情况。没有全十公司/390验收、旧全部历史/归档身份扫描、完整CI/发布/正式采纳验证。既有窄范围、减值和合约语义 helper 只检查本次接入关系及指定现有样本，不重新证明其整个语义覆盖。合成重选探针对既有语义 helper 使用明确返回替身，因此仅证明新一次重选、保留判断、失败出口和旧默认兼容；真实 Marriott/Salesforce 不替换该 helper。

结论 NEEDS_FIX 仅针对上述两项新接缝；无需把本轮扩成全仓审计。

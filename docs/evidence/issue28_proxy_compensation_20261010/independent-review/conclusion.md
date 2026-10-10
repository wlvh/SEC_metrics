# 精确差异限定独审

结论：**LIMITED_REVIEW_PASS / NO_ACTIONABLE_FINDINGS**。在下述精确差异和检查边界内，未发现需要修复的错误接受、计算错误、引用错位或新增误拦截。本结论只覆盖公共 no-inline proxy 来源组件及其小型接线；不表示公司消费者已交付、真实材料已由本审阅者重放、完整 C03 验收或正式采纳。

- Base：`98e5312e2b1e5170724055a171942f9c10f337a6`。
- Reviewed head：`c1b141d4103c78f988e6fad38f0a0cb48642f2f8`。
- 工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-proxy-compensation/SEC_metrics`。
- UTC 开始：`2026-10-10 13:50:06 UTC`。
- UTC 完成：`2026-10-10 14:01:00 UTC`。
- 工具计数：`55 (18 functions.exec + 37 nested tools)`；保守计数同时包含每次 functions.exec 外层和其每次 nested tool 调用。无协作工具调用。
- 普通消息计数：3（开工告知、一次进展、最终回复）；问题 0。
- 新 provider / paid / SEC 调用：`0 / 0 / 0`。自写控制脚本禁止 socket connect；未运行网络、真实调用、commit、push 或打包。

检查范围为 proxy_compensation_source.py、proxy_source_identity.py、organization_name_core.py 与 historical_board_composition_v2.py re-export、ordinary_current_update.py 的 C02 依赖增量、C03 Spec 与它的 presentation override、两个新测试模块及 workflow step。读取既有共同函数仅用于确认这些接缝的实际消费关系。旧 C03 namespace 修复不重审；未检查 #47 工作目录状态。

## 已核实的关键行为

1. **来源身份和字节先于结果成立。** 新组件重用 RawBlob/SourceReference 验证以及原 public SEC URL 检查，要求实际 bytes 的 hash、长度、HTML media、公司、governance_proxy role、accession、primary document、URL 中的 CIK 和所选 filing 一致。DEF 14A 元数据与封面唯一勾选的 Definitive 相互核对；同 CIK 的 SEC 当日有效名称仍独立核对。要求本地正文完整；任何 inline XBRL 元素的既有识别方式仍拒绝本 fallback。定向源码核对及负例均未显示放宽。

2. **原解析和指标含义保留。** 从固定 `bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786` 比对，八个 table/name/amount/arithmetic 函数的 AST 完全相同，六个 cover/date/name 函数的 AST 完全相同，原 Spec 逐字节相同。`_need` 差异只是本模块异常类名称。新 resolver 另增加 target/company、fiscal-year 类型/范围、inventory CIK 和正文完整性检查，没有另建求和、人员、年度或单位规则。原和数不符、异币、缩放、无美元、错表题年份、多个 CEO、业务单元 CEO 与完整正文负例由所需测试实际执行。

3. **尾部脚注引用修复成立。** 当 Total 为 `1,500,000`，后面另有 `7` 或 `(7)` 单元格时，计算仍为 `1500000`，引用恢复到 Total 单元格。单独脚注在 Total 前的控制也通过。一个真实金额为 `7` 且原行已正确求和时保留该金额；破折号零金额也保留。五个追加正例均用真实 native resolve_cell 重读 locator，并比较 reported_raw_text、amount/table locator、最后一个 witness 与 derived asset 的父原件引用，没有用成功替身。

4. **普通输出的组合可用。** 两个构造记录经实际 render_ordinary_records 执行：唯一 CEO 加尾部脚注显示 `PROXY / MDA_OK / 1500000`，证据引用为 `Source table cell: 1,500,000`；两个 CEO 显示 `PROXY / WITHHELD`，无标量或金额证据。二者保留 DEF 14A 与所选 proxy accession，receipt 明示构造来源、无 production 权限。这只验证 renderer 接缝，不能替代原件来源证明、公司 CLI、保存、重复运行或独立读者验收。

5. **名称 helper 只有一份且版本比较有效。** helper、v2 re-export 和 helper 测试与固定 `4bcf6fbf9b92337940c6321eb84e1f1d10b9330c` 逐字节相同。既有显式 COMPOSITION_GROUPED_V2 经 c02_composition_text_results._prepared 实际调用 v2 selector；v2 直接导入该 helper。C02 配置加入 helper hash；只变 helper 时 C02 配置改变，B01 和 C03 默认配置不变。显式 SCT 的 PROCESSING_FILES 包含 helper、identity、table/parser 与新 Spec；deterministic_router 等共用依赖由既有普通配置提供。没有把 helper 加入 shared 全局政策列表。旧默认 C03 仍没有自动进入 SCT 的接线。

6. **workflow 仅增加这两个测试模块。** 环境保持 PYTHONDONTWRITEBYTECODE 与原 PYTHONPATH 形式，没有改其他验收步骤。指定文件的 `git diff --check` 成功。

## 本审阅者实际运行

所需命令：

```text
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_proxy_compensation_source tests.vnext.test_organization_name_core
```

`required-tests.log` 记录 **14 tests / 3.039s / 0 failures / 0 errors / 0 skips**，退出码 0。这里使用实际观察到的时长，不沿用预估 0.1s。

另运行 **21 个独立定向控制**（14 个来源/目标拒绝控制、5 个金额与引用正例、1 个固定 Git 出处比对、1 个配置依赖控制），全部通过，见 `boundary-controls.log`。非 SEC URL 在既有 SourceReference builder 处已拒绝，这一条没有声称到达 resolver。第一次自写 harness 将 source assembly 放在 try 之前，因此在预期的 URL 拒绝处退出 1；保留 `boundary-controls-initial.log`，纠正 harness 后完整 21 控制退出 0，未改源代码或测试。

另有 **2 个实际普通 renderer 构造控制**，退出码 0，见 `ordinary-render-controls.log`。合计计数不等于新增公司或业务验收数量。

## 未覆盖与后续责任

- 作者 README 和 saved-tables.json 中 Macy、Marriott、JPMorgan 三份真实原件检查只作为输入参考；本审阅者未重读其完整原件，也未自称复现那些值、原件 proofs 或耗时。记录中声明的工作树测试阶段与 reviewed commit 阶段没有混写。
- 不授 native Run、公司 CLI/store/CSV、禁止重复计算、独立保存结果读者、最新年度更新或完整 C03 信用；这些仍由显式 selected-year 消费者完成其正常链路。当前组件没有来源获取或选取后续 proxy 的权力。
- Proxy amendments、未保存材料、尚不支持的封面/表布局及未解决的期间/人员案例继续遵守其既有边界。本次没有改变业务口径或归因标准，也未为所有未来布局作正确性保证。
- 未执行完整大材料套件、GitHub CI 或实时 Issue 查询；委托明确禁止 network，故不对实时授权、合并、采纳或生产状态作判断。

达到限定差异的合理检查终点后停止；未触及 80 工具、90 分钟或 3 普通消息上限。初始工作树干净；新增文件只在本 independent-review 目录。

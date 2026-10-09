# 01a007f URI 与本地名筛选修补限定复核：PASS_LIMITED

对象：`01a007f9fa2a76339c5b81c0e1c18a8612c8ca26` 相对 `44c8b22a6fd7a4ba309f1c0e458355ce274f5cbf` 的单项 P2 修补。范围仅 `scripts/vnext/b03_contract_amortization_scope.py` 中 `_selected_original_facts` 的共同候选筛选，以及 `tests/vnext/test_b03_current_input_scope.py` 新增的同名公司扩展概念反例。继承 `independent-b03-p2-44c8b22/conclusion.md` 与其 `independent-probes-source.log` 的已通过结论，未重审既有 B03 全模块；旧 NEEDS_FIX 原件未改。

- 起始 UTC：2026-10-07T00:26:20Z。
- 结束 UTC：2026-10-07T00:29:02Z。
- 实际工具调用：26次，按外层与实际嵌套工具均计的保守口径：9次 functions.exec＋17次实际工具（15次 exec_command、2次 apply_patch）。shell命令及Python子进程不另计工具。未到80次/90分钟上限。
- 普通消息：3条（2条进度及1份最终报告）；问题0。
- 没有 spawn、修改源码、commit/push、模型/SEC请求、账户或 #47 操作；只新增本目录的 conclusion.md 与日志。实时读取 Issue #28 当前正文，未恢复已取消的防篡改工程要求。工具读过的记忆索引无本项相关命中，未用于业务结论。

## 本项结论

没有发现本次修补范围内仍需修复的问题。命名空间 URI 表示概念实际属于哪套词汇，本地名表示该词汇中的具体名称；前缀只是文档里的短写法。新条件先同时匹配受支持的 FASB URI 与选中概念的本地名，无关公司扩展事实因此在核对已选标准事实前被略过。合法标准事实随后仍按原代码核对主体、年度起止、无维度、USD及数值，缺少有效事实仍触发 `SELECTED_COMPONENT_NOT_IN_ORIGINAL`。

基线函数仅从指定 base 的 Git 原件抽出并实际执行，同值7和异值999的公司扩展 `issuer:Depreciation` 均仍触发旧 `SELECTED_COMPONENT_NAMESPACE_MISMATCH:depreciation`；当前真实 helper 与 `inspect_depreciation_input` 对同一原件均只保留标准7＋13，结果 KEEP/20。这排除了探针没有进入旧错误分支的解释。

## 实际验证

指定命令由本审阅者执行，9项、0.031s全部通过（`required-tests.log`）：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B -m unittest tests.vnext.test_b03_current_input_scope.CurrentDaScopeTest -q
```

7项独立小输入探针、0.041s全部通过（`independent-probes.log`；源码保存在 `independent-probes-source.log`），覆盖37个有界组合：

- gaap/us-gaap/accounting三种前缀配http/https标准URI，共6组；均保持标准事实ordinal及7＋13。
- 折旧和摊销两个选中概念各自与同名公司扩展概念共存，扩展值同值或999，放在标准事实前、中、后，共12组；均只消费两个合法标准事实。
- 两个角色各自缺少合法标准概念但有同值扩展事实，共2组；仍拒绝。
- 两个角色各自的标准事实错CIK、错开始日期、错结束日期或非USD，同时存在公司扩展的正确主体/期间/USD同值事实，共8组；仍拒绝，未借用扩展事实补足标准概念。
- 同名合法标准事实有冲突数值，共2组；仍拒绝。
- 非标准URI或标准URI后追加路径/查询参数，共3组，以及标准URI但本地名不匹配，共2组；仍拒绝。
- 旧P2的同值与异值两组，均实际证实base误拒、head恢复上述有限正确行为。

重放命令：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B - < docs/evidence/issue28_company_records_20261007/independent-b03-uri-01a007f/independent-probes-source.log
```

`reviewed-patch.log`保存两处实际差异。`integrity.log`逐字节核对两个受审文件、旧结论及旧探针源码与指定HEAD一致；tracked tree无差异，新增文件仅本复核目录。

## 未覆盖

PASS_LIMITED仅结清这项同名不同URI造成误拒的P2修补。未重新审阅已通过的B03政策依赖、合同摊销表格关系、英语或会计含义、整个公司计算、十家公司390结果、全CI、模型真实性验收、历史身份接续、合并/正式采纳/发布/部署或active切换。独立探针使用完整可解析的小合成原件，不声称现有十公司原件发生了同名碰撞，也不声称证明全部D&A业务范围完整。

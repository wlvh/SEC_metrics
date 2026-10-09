# 44c8b22 两项 P2 修补限定复核：NEEDS_FIX

对象：`44c8b22a6fd7a4ba309f1c0e458355ce274f5cbf` 相对 `b9228566e24ec8bd175c3f47a4bfc3a6f044bb51` 的修补。只复核 updater 的 B03 政策依赖、两项范围 helper 的概念/维度/成员别名处理及新增回归；继承前次审阅范围，不重审已覆盖 B03 全增量。实时读取 Issue #28 的2026-10-06内部工具简化决定，未恢复旧防篡改要求。

- 起始 UTC：2026-10-07T00:13:50Z。
- 结束 UTC：2026-10-07T00:19:32Z。
- 实际工具调用：40次，按外层与实际嵌套工具均计的保守口径：15次 functions.exec＋25次实际工具（21次 exec_command、2次 write_stdin、2次 apply_patch）。shell命令及Python子进程不另计工具。未到80次/90分钟上限。
- 普通消息：3条（2条进度及1份最终报告）；问题0。
- 没有spawn、修改源码、commit/push、模型/SEC请求、账户或#47工作区/账本操作。只输出本目录的conclusion.md及日志；探针夹具使用临时目录。旧NEEDS_FIX及probes.py未修改，已逐字节对照指定HEAD。

## 尚需修复：[P2] 按本地名先选，再把无关命名空间当成已选事实的错误

位置：`scripts/vnext/b03_contract_amortization_scope.py:34-45`，由`ordinary_b03_input_scope.py:63`调用。

命名空间URI指明“这个概念属于哪套词汇”，冒号前的前缀只是那套词汇的短写法；同一本地概念名属于不同URI时，并不是同一概念。本次修补删除前缀字串比较后，先只按本地名选择事实，随后对所有同名事实强制要求FASB URI。因此，合法`us-gaap:Depreciation=7`、`us-gaap:AmortizationOfIntangibleAssets=13`旁只要出现公司自定义`issuer:Depreciation`，便抛出`B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NAMESPACE_MISMATCH:depreciation`，即使自定义事实也报告7、与选中数值完全一致。

独立探针从base的Git原件抽出同一helper并实际执行：原base从同一小原件核对7＋13成功，只消费标准概念ordinal 1、2；patch的真实inspect_depreciation_input却在新的local-name分支抛错。先以自定义值9复现，再仅将它改成7排除数值矛盾解释，两次均实际进入目标分支。原件CIK=195、年度2025、USD及标准7＋13未变；没有伪造FASB URI，也没有调用身份替换。见`independent-probes.log`及`independent-equal-amount.log`。

建议：候选原件事实先同时匹配获支持的命名空间URI与本地概念名，再执行同公司/期间/单位/数值核对。其他URI的同名事实不应成为该已选标准概念的namespace mismatch；完全缺少合法标准原件时仍由现有“selected component not in original”检查扣留。补同名不同URI共存回归即可，无需扩展英语语义规则。

这不证明十家公司现有原件发生了该碰撞，但它是本次选择条件修改引入、可用完整合法小输入复现的误拒。原来的合法前缀单独替换问题已经修复，第二项P2的URI定位修补仍不完整，故整体NEEDS_FIX。

## 已实际验证通过的修补

第一项P2的政策依赖已修复：B03的processing_files加入`catalog/r6/text_results_v2_policy.json`。独立探针复制实际程序依赖到临时根，不mock文件摘要，仅修改该JSON的真实字节；配置差异恰好只有该路径。真实run_once先在未变条件下复用，政策变化后进入create_saved_result。故意让计算替身抛错时返回INPUT_OR_EXECUTION_FAILED并保留旧状态，没有复用旧结果或冒称新计算成功。配置比较、实际文件读取及updater判断均未替换；来源准备、旧记录读取与计算工厂为明确的小状态替身。

第二项P2的原复现已通过：组合7＋13使用gaap、us-gaap及accounting三种合法前缀均KEEP/20；直接D&A的三种前缀保留同一选中ordinal。组合及直接路径的错CIK、错期间、非USD、带维度和无有效标准命名空间等有界反例仍扣留/报错，原件摘要不匹配仍拒绝。

独立读取已保存Marriott FY2025原件，直接从事实流核对145m折旧与313m摊销。只改us-gaap概念、srt维度、mar自定义成员、iso4217货币前缀，分别及同时替换五组夹具：均保持5项合同摊销事实、相同resolved_dimensions、原135m费用收入扣减及逐表加减关系；未把派生别名夹具记作新SEC获取。保留事实但取消表格关系后仍返回COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED；原件摘要错仍拒绝。此探针未重新计算整家公司B03。

## 本次命令与日志

指定命令由本审阅者实际执行，42项、8.060s全部通过（required-tests.log）：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B -m unittest tests.vnext.test_b03_current_input_scope tests.vnext.test_b03_calculator tests.vnext.test_ordinary_current_update -q
```

6项独立探针实际运行5.860s，5项通过、1项因上述产品误拒失败。精确可重放代码位于independent-probes-source.log：

```text
TMPDIR=/private/tmp /private/tmp/issue28-company-c02-venv-20261006/bin/python -B - < docs/evidence/issue28_company_records_20261007/independent-b03-p2-44c8b22/independent-probes-source.log
```

同值7的单项确认实际运行0.027s，仍因相同产品误拒失败。首次同值确认的测试入口写错globals，未进入目标，错误保留在independent-equal-amount-initial-harness-error.log；修正入口后才得到上述确认。指定42项的首次输出收集也因zsh的status为只读变量报错，测试已完成且日志为OK；没有把收集错误写成产品失败或借用父执行结果。

reviewed-patch.log保存本次四文件差异；issue28-current.log保存本次实时正文；integrity.log核对四个受审文件及两个受保护旧审阅文件与HEAD字节一致。结束时HEAD仍为指定SHA，tracked tree无差异，新增文件仅本审阅目录。

## 未覆盖

没有重审既有完整B03实现、扩展会计分类或英语判断，没有全十公司/390验收、完整修订/继承主体材料、全CI、旧全部历史身份、合并/采纳/发布/部署验证。未验证长期进程中的政策热加载；本次政策结论限实际字节变化参与配置比较并触发计算入口。原有Marriott/Salesforce及Calculator材料仅按指定42项命令实际覆盖，不继承父执行信用。当前发现不要求扩成全仓审计。

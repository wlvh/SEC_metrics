# D02 附注页眉：有限共用读取修补

接续 [44ed9a9d 的原请求/原件对照](https://github.com/wlvh/SEC_metrics/blob/44ed9a9d9cc9997de4f057c57cb97213632cb7ae/docs/evidence/issue47_d02_saved_consumer_contract_20261013/README.md)。Ford FY2025 主干来源候选比原正确结果多8个重复页眉。本批仅接续既有 D02 读取核心，公共负责人已明确没有并写 `text_business_candidates` 与 `d02_text_results_v3`；模型IO、公司分派、controller/store/renderer仍由#28维护。

## 实现与保留边界

`d02_text_results_v3.select_d02_page_furniture` 接受已准备完整原件文档及候选，沿原历史页码关系识别同位置重复的页眉。额外要求页眉组紧邻实际附注标题；continued标题必须完整对应已定位的原附注标题。重复本身、出现在页首本身，都不能删除产品/案件标题或正文。不使用公司/年份特例、关键词法律理解器或任意调用者正则。

初测反例显示，仅使用旧页面位置规则会误删每页重复的产品名，原失败保存在 `controls.log`。修后保留此反例及没有页码的重复标题/正文，另拒绝错来源、错块、错原文位置。Ford初版只处理了6个块，最后两个位于下一附注标题前；补齐实际下一附注的版式锚点后，正好去掉已定位的8个页眉，没有删掉任何原披露。

`d02_text_results_v3.prepare_business_text_sources(..., d02_page_furniture=True)` 显式消费该函数，并把所选规则及删除块的原始位置留在覆盖记录。默认False输出与原读取保持；C02不得借用该参数。D03候选、完整文档、SourceReference、Item3/Item8/附注范围和事实金额读取保持。后继参数已贯穿既有 candidate→Evidence 原件重建：选择不同规则不能误用同一候选。旧V2文件、H1合同、原回答/失败/Run未改。

这不是已经接入公司的新 D02 Result。公共保存回答消费者须显式选择后继读取，并登记这两个实际模块及参数；它不能以修改了默认读取器的名义给旧请求补结论。本方没有新增调用器、普通保存器、控制器或另一历史pipeline。

## 实际结果

- 小输入与原H1材料：53项、0.331秒、零失败/错误/skip，见 `final-controls-fixed.log`。最初37项真实重复标题失败、搬测试时漏导入造成的3个harness错误分别保留，未拿导入错误冒充生产缺陷。
- Ford FY2025：全文准备2.508秒、原生candidate2.524秒、独立Evidence重建2.548秒/PASS。53→45，恰好保留原完整结果的45个原文/节/SourceRef/docID/raw跨度；删除8个页眉的原始块位置有记录。D03原候选完全相同，原完整单块Item8请求7f0d2be2及原回答仍匹配，不裁旧回答。见 `ford-source.json`。
- 第二个已保存来源 Ford FY2024：56→48；默认准备2.676秒、显式后继2.695秒，完整文档与D03保持；只删除页眉，不加载该年的模型答、不创建MetricResult/Run。见 `ford2024-source.json`。最初receipt取错proof字段的KeyError及随后更正保留，首次失败的耗时没有补造。
- 可移植驱动实际在FY2024执行完成，仍56→48、Evidence PASS，见 `ford2024-portable.json`/`portable.log`。驱动是两个已有Ford样本的源检查，不支持任意公司或非自然年，也不是对外公司pipeline。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_text_business_candidates tests.vnext.test_text_results_v2 \
  tests.vnext.test_legal_review_contract

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_d02_page_furniture_20261013/verify_source.py \
  --source-root /absolute/restored/source-inputs --fiscal-year 2024 \
  --receipt /absolute/new-output/ford2024.json
```

原件恢复沿正式历史指南和PR52已提交导出；来源只读，输出写新目录。新增真实SEC/provider/model均0，原35次调用、账本及旧结果保留。没有新模型方法轮次或完整业务接受。

新增4个用例全部在已登记的 `tests.vnext.test_text_results_v2.TextResultV2SourceTest` 中。实际 `run_foundation_ci.partition()` 将整个模块纳入source-material；现有vnext-fast工作流的source-material作业加载它，scripts/tests触发范围保留。没有追加无人使用的清单或另建runner；新head远端执行另核。

接续实际main18fa的B04/B07接收不重其150格普查。这份修补的公司保存回答/复跑/CSV仍依赖公共接缝；完整附注范围、其他D02语义缺陷及1950目标继续，不能把Source Evidence PASS当法律内容完整或五年交付。

正常合main18fa后，重跑同一53项受影响组合，结果见 `main-combination.log`；原件准备/模型材料未重跑，不把main升级重新记成模型执行。实际原件代码与合入前相同，原时间按其执行版本保留。

提交后的依赖精化：相同两个helper移到已有D02后继模块，共用 `text_business_candidates.py` 恢复为main精确字节，避免C02/D03因未使用的新函数遭文件版本误重算。函数AST除保留原异常类型的别名外完全相同，显式API/规则/选文/覆盖形状不变；53项受影响控制见 `isolated-dependency-controls.log`。不重Ford源材料、不把原耗时改签新head。公共消费者仍选择d02_page_furniture=True，新增实现依赖仅已有D02后继模块，共用源模块仍按原实际调用保留原依赖。

## 接收P1：年份不能作为页码

已实际读取PR240的4254885159及接收者4254899999。新增完整原表结构反例先红：2022/2023/2024相邻年份旁的重复诉讼正文，紧邻continued附注标题，被误判页眉而删去，见`year-columns-before.log`。这不是“默认关闭所以无影响”即可搁置的问题。

修补只在页码集合排除1900–2100这些合理年份；年份文字仍在原文中，没有删源或修改回答。真实分页、重复案件标题、continued边界及默认旧路径断言保持。54定向0.336秒、零失败/错误/skip，见`year-columns-after.log`。复用先前完整Ford准备对象做改变的helper检查，仍恰好去8页眉、保45块/D03原样；未重全文解析/模型/case，见`year-guard-ford-reuse.json`。原两年材料和耗时保原身份，不能当新head完整源首算。

新head交原接收者亲复，旧5a绿灯不替P1修后CI。源模块/公司入口/IO分工保持，没有把有限修补变成第三轮模型试验。

# SHA 508c434 的限定独立审阅

**结论：存在 1 项 P2，包含关系的负例防护尚不足；本 SHA 不获得该机械关系模块的无问题独审结论。** 保存的真实 Ford FY2025 原件正例成立，显式默认兼容也成立。缺陷涉及把尚未证明的来源关系写成 REPORTED_INCLUDED；未观察到完整 B06 数值被错误发布，因为结果仍保留 WITHHELD/null。

## 固定范围与独立性

- patch：`508c4346d33d11fe218edd449c88d66d92564695`；base：`8588ccbbb1c91d81e0fb1a89dff3575214282549`。开工和终检 HEAD 均为 patch，三个审阅文件逐字节与该提交一致。
- 只审 `scripts/vnext/industrial_lease_relation.py`、`scripts/vnext/ordinary_special_debt_scope.py`、`tests/vnext/test_industrial_lease_relation.py`。必要依赖只读追踪至已有原件/期间/主体/USD/维度检查、精度选择、可见表定位、附注 continuation/ordinal 绑定；未审完整 B06、完整财报、Run 或其他工作树。
- 先读代码、指定旧来源阅读结论，直接核对保存原件 HTML157–159（打印页154–156），独立执行测试、原件正例和额外反例，形成下面 P2 后，才读取本批 README 与开发者测试/保存读回日志作对照。
- 输入原件根：`/Users/lyuhongwang/Developer/SEC_metrics`。HTML SHA256 `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`；XML SHA256 `35cb6e0ef1f84d5790c0fdf38abb363b92b65cd7f14ab8e0342968780e9efcfe`。终检重新确认原件未变。既有完整财报阅读仅按原绑定复用，没有冒称本次重读。

## P2：包含行的金额没有参与关系核对

定位：`industrial_lease_relation.py:31–34,47–73`。程序仅核对租赁金额不大于当前/非当前**总债务**，然后从该段找匹配标签，并检查租赁事实与总债务事实同在 DebtDisclosureTextBlock 中。程序未读取“Other debt (including finance leases) (a)”在已证明的当期工业列中的数值，也未保存该金额或把它与被确认包含的租赁数作关系核对。

在真实来源结构上的有界反例已复现：调用公开 `inspect_special_scope(..., reported_relations=True)`；在内存里只将 HTML 与 XML 中 **c-21 / FinanceLeaseLiabilityCurrent** 的同一当期工业事实，从 136 百万美元一致改为 1,000 百万美元，并重算两份模拟输入的 raw_asset_id；保持主体、期间、维度、USD、精度、当前/非当前段、全部表标签及 Other debt 226 百万美元、当前总债务5,550百万美元不变。该模拟输入经过本适配器的原件身份和原生数值检查，仍输出：

```text
Other debt（当期工业列） = 226 million USD
FinanceLeaseLiabilityCurrent = 1,000 million USD
current_debt = 5,550 million USD
lease_inclusion.status = REPORTED_INCLUDED
additional_debt_amount = 0
```

该原表已把折溢价/发行费另行列报；目前没有任何来源关系可解释 1,000 如何完整包含于标明包含租赁的226。直接出现关系冲突时，不能仅因为 1,000 ≤ 5,550、标签相同及同在一个附注，就确证这笔租赁已被包含。这个反例不证明真实 Ford 原件错误；它证明新增判定会忽略限定范围内的直接数值矛盾。现有“excess”测试只使用超过 parent 总额的101/100，所以没有覆盖这条路径。

建议限定修复：把已证明工业当期列的包含行金额、单位/倍率和所关联脚注一起作为关系证据，遇到包含金额冲突或关系未建立时保留 UNRESOLVED；增加 **包含行 < 租赁 ≤ 总债务** 的负例。修复不需要扩建完整 B06 或通用语言判定，也不能以默认结果仍 WITHHELD 代替关系正确性。此审阅没有实施修复。

完整重现输出、修改计数和模拟字节摘要见 [independent-controls.log](independent-controls.log)。每份模拟原件只修改1个原生事实，均仅在内存；保存原件没有写回。

## 已确认的正确行为与验证边界

1. 指定命令的8项测试全部通过，0.001秒；覆盖排除标签、缺XML、超过总额、同精度冲突、错附注主体/期末、跨当前/非当前段及同值重复披露。原有错主体/期末防护与两项已修复反例保持有效。日志见 [unit-tests.log](unit-tests.log)。
2. 保存原件 Note17 的工业当前/非当前租赁136/754和 Note18 相应债务段/脚注(a)与程序正例一致。公开 `prepare_special_debt_case(..., reported_relations=True)` 实测3.076秒：债务21,919百万美元、租赁890百万美元、追加额0，record_type V2；两项工业限制同时保留，definition_complete=false，ratio=null，B06 WITHHELD/null。见 [source-pages.log](source-pages.log)、[saved-case-summary.log](saved-case-summary.log)及完整 [saved-case.log](saved-case.log)。这是来源准备信用，不是完整B06/原生Run/CSV/生产信用。
3. 从指定 base 用 `git show`加载原实现，对真实保存原件执行原 API；其整个 case 与 patch 默认 API、显式 reported_relations=False 的整个 case 完全相同，case_id `sha256:7a68af48bbdaf52f1f736c442629b8436c9859cc46e3b5dafc1759971edbe57c`。None、1、'true'均被拒绝为 REPORTED_RELATIONS_OPTION_INVALID。没有发现默认 API 兼容退化；见 [independent-controls.log](independent-controls.log)。
4. 对照开发证据：最终8项通过、默认case摘要、真实原件正例与独立复现一致；初版两个失败日志保留旧意义。开发者的磁盘保存/读回脚本会写另一路临时文件，本次没有重跑它；仅对默认case做内存JSON往返。没有授予额外持久化或冷读信用。

本次发现的是**错误确认部分来源关系**；没有将标签或程序PASS提升为完整B06信用。8项测试的重复披露/当前非当前防护通过，不等于对任意披露布局无误拦截的承诺。

## 执行与资源登记

- 开始UTC：`2026-10-07T21:06:08+00:00`；结束UTC：`2026-10-07T21:13:43.297408+00:00`；约455.3秒。
- 工具调用总计 **25**：12次外层 functions.exec、12次嵌套 exec_command、1次 write_stdin；包括本次结论写入及最后 HEAD/字节/原件核验。硬上限80未触及。
- 普通消息 **3**：开工告知、一次进展告知、最终报告；问题0。未再spawn子代理。
- 新增真实 provider/paid/SEC/账户请求均0；未执行网络调用、长测试、ledger申领、commit/push、tar.xz、Run/生产/active动作。
- 只写本 independent-review 目录的1份 conclusion.md 和5份日志；源码、旧证据与原件不改。

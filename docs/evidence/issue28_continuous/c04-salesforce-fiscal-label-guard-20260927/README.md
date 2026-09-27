# Salesforce C04：两份真实来源身份之间的财年标签冲突

这是一项只读、零调用核对，不修改C04代码或旧原件。`verify_guard.py`重新从#28原保存来源准备当前Salesforce年报，验证来源准入和主文件SHA；与[既有财年标签检查](../successor-source-components/fiscal-label/salesforce.json)及[既有390索引](../d04-remaining-20260922/current-390.json)比较。`verify.log`记录实际执行结果。

三者的**期间日期一致**：2025-02-01至2026-01-31。但普通输入直接使用原生DEI `DocumentFiscalYearFocus=2025`；同份已验证年报的可见定义明确把截至2026-01-31称为 **fiscal 2026**；旧390索引的Salesforce C04也按FY2026保存历史Result。Company Facts同申报相关`fy`字段为2025，不能消除此冲突。当前输入若未经口径修订就进入新C04 Run，会把同一实际期间从FY2026重标成FY2025，因此本轮没有生成新Run或改签旧Result。

此外，一份FY2025前期年报的原请求日志把实际SEC URL `crm-20250131.htm` 标作本地文档名`0002.body`，冻结V2年报核对因此先报`C04_SAME_CIK_FILING_REQUIRED`；该独立实现缺口见[来源核对](../c04-salesforce-current-20260927/README.md)。只修这个别名而忽略财年冲突，仍不能形成可接受的当前结果。原请求日志、SourceReference、既有390行和安装包均未改。

后续需把两项分开：别名在显式后继中用原始请求证明作向后兼容准入；FY标签优先级属于业务规则决定。已有`fiscal_year_labels.py`只提出来源定义FY2026，并**未**替当前普通输入或旧Run正式变更规则。无批准前保持新Salesforce C04 Run停止；此处没有模型、SEC、生产或#47信用。

# bd1e1dd 自身原生包含行读取的限定独审

**结论：NEEDS_FIX，存在两项 P2。** 两条旧金额反例现在正确保留 UNRESOLVED；自身原生金额、USD、HTML/XML 对应事实读取及保存/default兼容的正例成立。但新方法仍可能误接不同业务范围的包含行，以及接受原生倍率与原表声明的直接冲突。未观察到完整 B06 被错误发布。

## 固定范围及旧结论

- patch：`bd1e1ddbc9ffac750ea32b85fdd4bf03f1acf9b5`；base：`52b570b4cd9be97cb9ff692d1eefddb3c631718d`。开工与终检 HEAD 均为 patch，三个指定源码/测试文件与 patch 字节一致；只审本次新增方法和参数/JSON接线，不重开全模块。
- 先读 `../independent-review/conclusion.md` 和 `../independent-carrier-repair/conclusion.md`；原两份 NEEDS_FIX及未变范围保持，旧失败不改记通过。终检亦确认两份旧结论未变。
- 实时只读 Issue #28（updated_at `2026-10-07T21:37:51Z`），按受信任内部数据工具前提检查普通来源/解析错误；不建设防执行者作弊机制。只检查保存原件局部表/单元格和上下文，未重读完整财报、完整B06、Run、CSV或公司长链。
- 原件根 `/Users/lyuhongwang/Developer/SEC_metrics`；HTML `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`、XML `35cb6e0ef1f84d5790c0fdf38abb363b92b65cd7f14ab8e0342968780e9efcfe`，终检保持。

## P2-1：用前缀文字判断父级范围，未比较实际维度名称

定位：`scripts/vnext/industrial_lease_relation.py:18–26,55–59,73–77`。XML/HTML 中的 `f:...` 是缩写；它真正指哪个维度成员，需要同时看该处绑定的命名空间，即 QName。新 `_scope_matches` 仅比较原始缩写文字；后续 `_verified_context` 虽取得完整 QName，额外维度检查只检查新添的债务分类轴，没有把包含行继承的业务范围 QName 与总债务的已验证范围比较。最后 `_context_key` 只核对包含行两份原件之间，不能补上与父级范围的缺口。

小解析器输入和保存 Ford 原件结构均复现：仅在 `c-696` 的 context 起始标签，为 HTML/XML 各加入一次局部 `xmlns:f="urn:other-business"`。标签、原始维度文字、公司CIK、期末、金额、USD、两源间对应关系、当前工业列和附注位置都不变，分别重算模拟 raw_asset_id。当前总债务 c-21 的成员仍属于 `http://www.ford.com/20251231`；包含行的同名成员已属于 `urn:other-business`，两者不再是同一个业务范围。两份原件的包含行完整 QName 彼此一致，因此程序仍输出 `REPORTED_INCLUDED`、追加额0。这是来源范围被错误确认；模拟输入没有获取信用，原件没有写回。

同一个根因也产生误拦截：仅把 XML c-696 中共享业务轴/成员改用 `g:`/`ff:`别名，仍绑定原来的命名空间及成员，完整 `_context_key` 与 HTML相等，所有业务事实不变，结果却变为 `UNRESOLVED`。错误出在前面的原始文字筛选，后面的 QName 配对根本没有机会运行。

建议限于新方法：使用父级已验证的维度 QName 与成员 QName 核对继承范围，并按同一表示选择允许的额外债务分类轴；相同 QName 的合法别名应可对应，不同 QName 的同名文字应保持未决。无需改变指标口径或扩建通用语言判断。细节见 [independent-controls.log](independent-controls.log) 和 [independent-real-source-controls.log](independent-real-source-controls.log)。

## P2-2：自身数值与XML一致，仍不能覆盖原表明确的单位矛盾

定位：`scripts/vnext/industrial_lease_relation.py:61–65,84–86,130–134`。新读取正确使用包含行自身的 scale，解决了旧“借总债务倍率”的具体路径；但没有核对该数值与包含行所在原表的明确单位说明。当前只检查租赁不大于包含行，包含行倍率放大后的明显来源冲突会通过。

真实保存来源的该表前原文明确为 “as follows (in millions)”；当前工业列可见包含行226，总额5,550；原包含行自身 scale6/XML226000000。独立反例仅将该事实自身 scale6改9，XML226000000一致改为226000000000，其他全部来源字节与表声明/可见数字保持原样，模拟输入重新绑定 raw_asset_id。新原生解析确认两份包含金额都是226,000,000,000 USD，当前总额仍5,550,000,000，当前租赁136,000,000。程序仍给出 `REPORTED_INCLUDED`、追加额0，保存 inclusive_amount为226,000,000,000。

这不是要强制每个单元格采用相同 scale属性，也不建议单凭包含行超过总額做通用会计规则。这里是原表明确的“百万”及可见226，与所接受的2260亿美元数值直接冲突，精度不能解释千倍差异；XML一致仅证明两份标记一致，不能消除同一来源的可见披露矛盾。需在这个已支持表关系范围内核对原生金额与原表单位/可见金额，冲突时保留 UNRESOLVED。原 scale3 小金额反例虽已拦住，不能据此把原单位冲突责任整体结案。见 [source-unit-and-precision.log](source-unit-and-precision.log) 与 [independent-real-source-controls.log](independent-real-source-controls.log)。

## 已确认的行为与证据边界

1. 指定 unittest **11/11通过，0.025秒**，使用实际小解析器输入；见 [unit-tests.log](unit-tests.log)。指定两条原件反例脚本均成功完成：租赁1000百万/包含226百万，以及自身scale3/包含226000USD，均得到 UNRESOLVED/null，见 [amount-conflict.log](amount-conflict.log)、[own-scale-conflict.log](own-scale-conflict.log)。
2. 独立12项小输入检查中9项符合预期，3项暴露上述两类问题（同QName不同前缀误扣留、同文字不同成员命名空间误接受、金额放大直接冲突误接受）。另3项精度检查符合预期：XML更细且在舍入区间内可选、超出区间时报错、未知精度时报错。非USD两源、缺对应XML金额、同精度金额冲突、正确不同自身倍率与等于租赁边界均检查过。只承诺这些有限布局/关系，不扩成任意财报保证。
3. 保存原件正常来源仍为 `REPORTED_INCLUDED`：当前包含226百万/租赁136百万，非当前包含1210百万/租赁754百万，总租赁890百万，追加0；主接口仍保留工业归属权益/债务完整性限制，definition_complete=false、ratio=null。来源准备信用不等于完整B06信用。
4. 指定 persistence 脚本逻辑成功运行，只将其固定 `/private/tmp` 文件路径在内存换成隔离随机临时目录并在结束删除，脚本源文件没有修改；避免覆盖开发者的已有临时结果。JSON写盘/严格读回后整个case一致，保存2394398字节，case_id `sha256:a719850604cb1550f2fa671d1f0e81611600a5581bdcc56df6655d5abd7e666a`，B06仍 WITHHELD/null。另以本次指定base52b570b的源码在内存加载，证实**整个case**的base默认 == patch默认 == patch显式False，默认case_id `sha256:7a68af48bbdaf52f1f736c442629b8436c9859cc46e3b5dafc1759971edbe57c`；None/1/'true'仍拒绝。见 [default-and-persistence.log](default-and-persistence.log)。
5. 独立复现后对照开发direct-*证据，旧两条金额反例、默认身份及持久化结果一致；其正例不覆盖本次新发现的QName父级范围及放大倍率冲突。

## 执行与资源

- 最早UTC捕获 `2026-10-07T22:12:12.754973+00:00`；结束 `2026-10-07T22:18:43.466768+00:00`，捕获区间 390.712秒；包括此结论写入及最终核验，远低于90分钟。前两次只读工具在首次UTC捕获之前，工具计数包含它们。
- 工具总计 **35**：17次外层 functions.exec、15次嵌套 exec_command、3次 write_stdin；80上限未触及。
- 普通消息 **3**（开工、一次进展、最终），问题0；无spawn/恢复旧agent。
- 新provider/paid/SEC/账户请求各0；GitHub仅只读Issue28一次。无commit/push、#47操作、tar、long tests、真实model/SEC、Run或生产动作。
- 仅新增本目录一份 conclusion.md、九份日志；源码、旧材料、保存原件未改，终检 tracked diff为空。首次真实反例设置因XML context使用默认命名空间而失败，已在 [real-control-setup-failure.log](real-control-setup-failure.log) 保存并按实际结构重跑；不把设置失败记成产品错误。最终字节/资源核验见 [final-byte-and-resource-verification.log](final-byte-and-resource-verification.log)。

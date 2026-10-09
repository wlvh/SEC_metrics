# 48b2417 QName 与可见单位新差异的限定独审

**结论：NEEDS_FIX，旧两项 P2 在本差异中已修正；新增一项 P2 单位误拦。** QName 相同的合法别名现在通过，不同成员 URI 现在保持未决；原表明确百万但自身原生 scale9/XML 同步放大的旧反例现在保持未决。新单位读取仍把表前债务介绍里的任一外币词当成本表外币单位，因而拒绝原本已由 USD 原生事实、可见百万单位和包含行关系证明的来源。

## 范围与继承

- patch `48b24178707917d7c475854d53663773901f90d0`；base `bd1e1ddbc9ffac750ea32b85fdd4bf03f1acf9b5`。开工及终检 HEAD 均为 patch；指定源码、测试与 patch 字节一致。
- 先读 `../independent-native-carrier/conclusion.md`。只审 `industrial_lease_relation.py` 的父级 QName 继承、可见表单位及表前有界引言读取，以及对应新增测试。原生金额算法、原元组/JSON/default兼容及未变范围复用旧结论，不重新独审整模块、完整 B06、全财报或公司长链。旧 NEEDS_FIX 文件与历史原义保持。
- 只读实时 Issue #28 一次，按当前受信任内部工具与有限业务核对要求执行；无 #47 操作。保存原件根为 `/Users/lyuhongwang/Developer/SEC_metrics`。没有新增业务调用、Run、CSV或生产结果。

## P2：把债务币种介绍误作本表列报单位

定位：`scripts/vnext/industrial_lease_relation.py:108–118`，具体外币拒绝在 114–115。读取上一表结束到所选表起点的原文是有限范围，但这整个范围并不全是本表单位声明。当前对整个引言执行 `EUR/euro/GBP/pound/JPY/yen` 词匹配，发现任一词就返回 None；它没有区分“债务原来用什么币种”与“当前表用什么币种列报”。

独立保存原件控制只在 Ford 原表之前插入一条可见句子：`Euro-denominated debt is translated into U.S. dollars for presentation.` 原件其他字节、XML、包含行自身金额、上下文和维度、USD、当前工业列、原表明确 `as follows (in millions)` 及同附注位置都不变。新增段落没有新原生事实，重新绑定模拟 raw_asset_id；没有写回原件。完整 `inspect_special_scope(..., reported_relations=True)` 从原件正常 `REPORTED_INCLUDED/追加0` 变为 `UNRESOLVED/null`。原 226百万/136百万及1210百万/754百万关系没有发生业务矛盾，只因 Euro 一词丢失已有关系支持。该控制是内存派生反例，不是新获取来源或真实发行人原文。

同样的小解析器控制也复现；另一小控制在独立前句讨论以百万描述的此前发行、当前表 caption 明确 dollars 时，仍因收集整段引言单位而误拦。它仅作为同一范围绑定问题的辅助证据，不据此要求扩建语言理解平台。

建议限于已支持关系：将外币/倍率冲突检查绑定到所选表的明确单位声明或列头，保留真正外币单位和相互矛盾单位的未决；不能让普通债务介绍中的币种词直接推翻已核实 USD 表。无需新增一般财报语义引擎。见 [real-qname-and-introduction-controls.log](real-qname-and-introduction-controls.log) 与 [small-independent-controls.log](small-independent-controls.log)。

## 已修正的两项旧 P2

1. **父级完整 QName。** 新 `_scope_matches` 用命名空间 URI 与本地名称的组合核对继承维度及成员，允许合法别名，并把额外债务轴限定为标准 us-gaap LongtermDebtTypeAxis 及同命名空间成员。保存原件 XML c-696 的 g:/ff: 别名控制现在 `REPORTED_INCLUDED`；其派生 XML SHA `6b86f473c0d1667d578d924474a72c2a402561b00798f14d1ba430a4b9fda8b9` 与旧误拦反例相同。两源 c-696 局部改为 `urn:other-business` 的同名成员现在 `UNRESOLVED`；派生 primary/XML SHA 分别仍为旧反例的 `6035af117bd602aa54dfc13dbeee5f2f7863d42f64fc00ded270bd3c6b13001e` / `a67debda3ff7c678b7153e06f738ef45d0273f075623f199be607189ce01b4ec`。两源错误 QName 彼此一致仍不能绕过父级范围。见真实控制日志。
2. **原表单位与自身倍率。** 指定 `verify_own_carrier_scale.py <原件根> 9` 已实际完成、returncode0。当前包含行 scale6→9、XML226000000→226000000000而原表仍明确百万/可见226，现在 `UNRESOLVED/null`。这修正旧的千倍单位直接矛盾；没有改原生精度算法。见 [visible-unit-conflict.log](visible-unit-conflict.log)。

## 验证与限制

- 指定 unittest **13/13通过，0.037秒，零失败/错误/skip**，使用指定 Python 与 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts`；见 [unit-tests.log](unit-tests.log)。新增测试覆盖 XML 合法 QName 别名、不同 URI 及倍率与可见 dollars 冲突。
- 指定 `verify_saved_case.py --source-root <原件根>` **returncode0、3.519秒**：保存 Ford 原件仍 `REPORTED_INCLUDED`，租赁总额890百万、追加0；21919百万所报工业债小计保持，definition_complete=false、ratio=null，B06 WITHHELD/null，无 Run。见 [saved-case-positive.log](saved-case-positive.log)。
- 独立小输入共18控制：16符合预期、2暴露上述新范围/单位误拦。另验证两源合法别名、不同继承轴/成员 URI、漏继承范围、非标准额外轴/成员、缺单位、caption单位、同div引言、上一表不供本表单位、上一表冲突不泄漏、隐藏XBRL资源/script/style不供可见单位、真正外币与相互矛盾单位拒绝。自身 scale 与父级不同、但同可见 thousands/millions一致的两项正例均通过，未要求所有单元格 scale 相同。
- 保存原件独立3控制：原 QName 合法别名与不同 URI 的2项现在正确；新增外币介绍的1项误拦。所有控制满足实际解析和目标判断前置条件。不是任意财报/任意语言保证。
- 第一轮两条原件脚本完成输出后，外层日志命令使用 zsh 保留变量 `status` 导致 `read-only variable`。这是执行包装错误，未当作产品失败；保留 [harness-status-error.log](harness-status-error.log)，仅这两条指定短脚本各重跑一次并取得明确 returncode0。
- 原元组JSON/default兼容按未变范围复用；本次只读 `qname-unit-*`/`visible-unit-conflict.*` 与旧结论对照，不复跑原长材料，也不把默认兼容当新范围通过。

## 执行与资源

- 首次 UTC 捕获 `2026-10-07T22:38:30.029882+00:00`；终检 `2026-10-07T22:43:41.874198+00:00`，捕获区间 `311.844` 秒。开场两批只读工具早于首次捕获，纳入工具计数；未触90分钟。
- 工具总计 **40**：13次外层 functions.exec、21次嵌套 exec_command、6次 write_stdin。普通消息 **3**（开工、一次进展、最终），问题0；spawn0。未恢复旧代理、未改变其35次/3消息记录。
- 新 provider/paid/SEC/账户请求各0；GitHub仅只读 Issue28一次。无源码/测试/旧材料/保存原件修改，无 commit/push、tar、长测试或 #47 操作。
- 仅新增本目录一份 conclusion.md 与八份日志；终检 tracked diff为空，三个初始指定文件 hash不变，目录外没有新增变化。最终字节及资源核验见 [final-byte-and-resource-verification.log](final-byte-and-resource-verification.log)。

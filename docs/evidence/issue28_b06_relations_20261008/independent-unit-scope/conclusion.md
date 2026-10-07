# 487b053 表格单位范围差异的限定独立审阅

**结论：NEEDS_FIX。原 Euro 业务介绍误拦已修复，但出现一项 P2：明确外币符号的表单位被忽略，冲突表被错误确认包含。** 该结论只覆盖 `visible_scale` / `introductory_text` 新差异与对应新增回归；不扩大为完整 B06 或公司结果信用。

## 精确范围与继承

- patch `487b0531d80bb028c2784a5ef5cf4bac42abdfdf`；base `48b24178707917d7c475854d53663773901f90d0`。开工与终检 HEAD 均为 patch；指定源码、测试与探针脚本的字节在执行前后相同，见 `initial-byte-verification.log` / `final-byte-and-resource-verification.log`。
- 读取 `../README.md`、`../independent-qname-unit/conclusion.md`、`table-unit-*.json/log` 和指定原件控制脚本。继承上一轮 QName 与倍率两项 P2 已修正的结论及原未变职责，不重新审阅原生金额/QName算法、完整财报、公司长链或旧 default 实现。指定小测试内的未变用例仍随套件执行，但不记成新独立全模块验收。
- 只读实时 Issue #28 一次；其当前受信任内部工具、有限业务核对及资源边界适用。不重建权限防伪框架。来源根 `/Users/lyuhongwang/Developer/SEC_metrics` 只作保存材料读取。

## P2：明确外币符号的表单位被忽略

位置：`scripts/vnext/industrial_lease_relation.py:116–119`；新增回归 `tests/vnext/test_industrial_lease_relation.py:89–94` 尚未覆盖符号币种。新差异移除了原对 `€£¥` 的检查，只在 `in euros/EUR/pounds/GBP/yen/JPY` 等词组匹配后拒绝。所选表 caption 的 `Amounts (in €)` 已被原表解析器读到，却不匹配新正则，因此被当作没有单位声明；另一个 USD 引言仍提供倍率，程序把存在明确外币冲突的表确认成 `REPORTED_INCLUDED/追加0`。

小型完整解析器控制只给既有有效 USD 事实、包含行和租赁关系增加 caption：`<caption>Amounts (in €)</caption>`。patch 错误接受；精确 base 源码在同一输入上保持 `UNRESOLVED`。`in £`、`in ¥` 与 `Amounts (€)` 也错误接受，前两种同样通过 base 对照确认是新回归。没有改变原生事实金额、主体、期间、单位或 XML。见 `independent-unit-controls.log` 与 `base-versus-patch-controls.log`。

保存 Ford 原表控制通过公开 `inspect_special_scope(..., reported_relations=True)` 再现：只在原 `table_000136` 的开标签之后插入上述 caption，实际解析后的 `caption_raw_text` 明确为 `Amounts (in €)`。原表可见百万及原生 USD/自身 scale6/XML 金额保持；新增 caption 已直接与这些单位冲突，预期必须未决。patch 仍给 `REPORTED_INCLUDED/追加0`，所报债小计仍21919000000。原 primary SHA `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`，派生 SHA `74797e6c318a7f2015fde88d009b13d73386c57c3197f471f26e93c3f076bfde`；XML SHA `35cb6e0ef1f84d5790c0fdf38abb363b92b65cd7f14ab8e0342968780e9efcfe` 不改。见 `saved-explicit-currency-control.log`。这是内存派生的矛盾反例，不是发行人实际披露或新获取来源；没有写回原件。

建议只在所选表的明确单位声明、caption/列头中保留已支持的外币符号冲突检查，并补三个符号负例；仍忽略普通业务介绍里的外币词。无需恢复对整个表前间隔的任意币种扫描，也无需扩建通用语言解析器。

## 已验证修复、回归与具体限制

- 指定 unittest **16/16通过，0.052秒，零失败/错误/skip**；进程墙钟0.368秒，returncode0。见 `unit-tests.log`。新增测试正确保留分段/同段/后置 Euro 业务介绍及普通较早发行说明，拒绝 `in euros`、`in millions of euros` 与明确倍率冲突。
- 指定 `verify_table_unit_scope.py <原件根>` **returncode0**，脚本计时6.107秒，进程墙钟6.423秒。原 SHA3bbda 与同一旧 Euro 派生 SHA8cbe 都为 `REPORTED_INCLUDED/追加0`，原误拦控制确已修复；仍 `definition_complete=false/ratio=null`。见 `saved-introduction-control.log`。
- 独立小输入19项：14项符合预期，4项为同一外币符号错误接受，1项为既有范围限制。正常 USD、同div引言、独立 `in USD` 正例通过；明确 EUR/GBP/JPY caption、euros 引言、倍率矛盾及缺单位负例保持未决。只证明这些输入形态，不证明任意财报语言覆盖。
- **仍未覆盖的表前范围：** 较早发行说明若自身以 `as follows (in millions)` 结尾，后面另有当前表说明且当前 caption 明确 dollars，`introductory_text` 仍向前回扫并选中旧发行单位，错误 `UNRESOLVED`。同一输入 base 与 patch 均未决，故不冒充本次新增回归、也不要求本轮扩通用语义解释。现有“Earlier issuance prose cannot supply that scope”注释与README的范围排除说法须按这个具体边界解释。该限制见 `prior_as_follows_issuance` 控制。
- 默认/JSON保存与旧长链只读复用 `table-unit-default.json/log` 等既有记录，没有重跑或扩大信用。scale9/两原件226b但可见百万仍未决的历史修复按 `table-unit-scale-conflict.json/log` 继承，不以新差异替换旧原义。
- 真实原表单位关系的局部正例继续成立，完整 B06 仍缺工业权益及债务完整性；没有新原生 Run、CSV、公司接受、合并/部署/active 或生产结果。
- 追加原件矛盾探针第一次直接把 `_InlineTableIndex.tables` 的 builder 当dict读取，在业务判断前抛 `TypeError`。设置错误已保留 `saved-currency-control-setup-error.log`；随后改用既有 `_fact_cells` 取展开表，一次取得上述业务反例。没有把探针设置失败当产品失败。

## 时间、工具与输出边界

- 起始 UTC `2026-10-07T22:51:15Z`；终检 UTC `2026-10-07T22:55:14.882642+00:00`；区间 `239.883` 秒，未触90分钟上限。
- 工具总数 **29**：10次外层 functions.exec、18次嵌套 exec_command、1次 clock；无 write_stdin、spawn 或其他代理。普通消息 **1**（仅最终报告），问题0、过程消息0；低于80工具/3消息上限。
- 新 provider/paid/SEC/账户操作各0；GitHub仅只读 Issue28一次；无 #47 工作树/运行根/账本操作，无源码/测试/旧材料/原件修改，无 commit/push、tar 或长演练。
- 仅新增本目录一份 conclusion.md 与八份必要日志。终检 tracked diff为空，三个初始指定文件 SHA不变。精确最终文件清单与资源记录见 `final-byte-and-resource-verification.log`。


## 89d2d64 明确外币符号修复的差异补充（沿原资源累计）

**补充结论：本次符号修复差异 PASS，487b053 新增 P2 已修正。** 上文 NEEDS_FIX 是对原 SHA 的历史结论，原文字及八份旧日志完整保留；本次不重审未变全模块、原 QName/金额算法、完整财报或公司长链。

- 精确 patch `89d2d64960e895dc52466af5dedd1f71b1ed7cd9`；base `487b0531d80bb028c2784a5ef5cf4bac42abdfdf`。新增源码仅对选定单位声明里的 `€/£/¥` 及独立符号作拒绝；`introductory_text` 与原单位词组读取未改。读取新测试/原件日志及脚本增量，执行前后 HEAD 和三份指定源文件字节不变。
- 指定小套件 **17/17通过，0.073秒，零失败/错误/skip**，进程墙钟0.393秒，returncode0；见 `unit-tests-89d2.log`。新增一个测试方法含三个符号 × `in 符号`、单独括号符号、`in millions of 符号` 共9个控制，全部未决。原分段、同段和后置 Euro 业务介绍正例继续通过，没有恢复对任意外币词的全间隔拒绝。
- 指定 `verify_table_unit_scope.py <原件根>` **returncode0**，脚本计时8.462秒，进程墙钟8.783秒，见 `saved-unit-scope-control-89d2.log`。原 primary SHA3bbda 与业务介绍派生 SHA8cbe 都保留 `REPORTED_INCLUDED/追加0`。上一轮实际外币 caption 反例 SHA `74797e6c318a7f2015fde88d009b13d73386c57c3197f471f26e93c3f076bfde` 完全相同，现在为 `UNRESOLVED/null追加额`。因此修正的是旧反例的错误接受，未通过更换派生输入清除问题。
- **具体未覆盖限制仍保留：** 较早发行文本自身以 `as follows (in millions)` 结尾时可能被选作当前表引言，尽管当前 caption 明确 dollars，造成误拦。该路径未改且本次不重跑；按上文 base/patch 同结果控制继承，不能把 PASS 扩为所有表前文本范围或任意财报语法保证。只验证既有三种符号及上述明确声明格式，没有增加通用语义处理能力。
- 局部包含关系正例仍 `complete_B06=false/ratio=null`。工业权益和债务完整性仍未建立；没有新 Run、CSV、完整 B06、公司结果、合并/发布/部署/active 或生产信用。未变 default/JSON/长链只复用旧记录，没有追加演练。
- 补充起始 UTC `2026-10-07T22:57:09Z`；终检 UTC `2026-10-07T23:01:26.010943+00:00`；补充区间 `257.011` 秒。原起始 UTC `2026-10-07T22:51:15Z`，累计区间 `611.011` 秒，未触90分钟。
- 本次8工具/1最终消息；累计 **37工具/2普通消息**（13次 functions.exec、22次 exec_command、2次 clock；问题0、过程消息0、spawn0），未触80工具/3消息上限。只跑指定17项 unittest 与指定保存原件脚本，各一次；无业务/账户/#47请求或操作，新增 provider/paid/SEC各0，无源码编辑或 commit/push。
- 仅对本 conclusion.md 末尾追加本段，新增4份带 `89d2` 后缀的必要日志。旧结论前缀逐字节不变、八份旧日志 SHA均不变，见 `final-byte-and-resource-verification-89d2.log`。

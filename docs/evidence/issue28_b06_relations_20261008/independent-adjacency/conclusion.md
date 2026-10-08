# 930a3df 显式本表单位与相邻引言：限定独立审阅

**结论：PASS（仅本次差异）。** 原 `prior_as_follows` 误拦在表内已有明确单位时得到修复；本表和紧邻引言直接声明的单位矛盾仍保持 `UNRESOLVED/null追加额`。本次限定范围未发现需修正的新增问题。缺表内明确单位的旧有限行为没有由此解决；不授完整B06、公司结果或生产信用。

## SHA、范围及历史复用

- patch：`930a3df29df8dbc8cd519044a23aeb682c09f80c`；base：`7ae99dfdca49ead83fdee669d158083c85714233`。开工及终检HEAD均为patch；源码、测试、指定控制脚本与patch的Git字节一致，执行前后未变，见 `initial-byte-state.log`、`final-byte-verification.log`。
- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-b06-relations/SEC_metrics`；来源根：`/Users/lyuhongwang/Developer/SEC_metrics`。后者仅供指定脚本读取保存来源。
- 判断范围仅为 `industrial_lease_relation.py` 的 `visible_scale`、提取但未扩词表的 `reporting_factors`、`introductory_text(adjacent_only=...)` 差异（当前96–175行），以及新增完整解析器回归（测试89–93行）。读取同文件1–263行及测试夹具作为调用上下文；没有重新裁定未变QName、原生金额、符号回修或完整B06职责。
- 已读同根README、`adjacent-table-unit-before/after/original/default` 日志及两个JSON。original/default的 `.log` 是空文件，实际结果在对应JSON。指定旧 `independent-unit-scope/conclusion.md` 的487b NEEDS_FIX、89d符号增量PASS与930资源停止记录均按原范围保留。本次是新委托从09:59:27Z开始的独立生命周期；旧代理未执行930测试的停止记录没有被当成完成信用。
- 已实时只读Issue #28；当前内部工具前提、保留业务单位核对与资源上限适用。没有新增权限或验收层级。轻量memory检索未命中本次单位/邻接差异，判断依据为本次Git字节、测试和保存原件控制。

## 为什么本差异成立

原代码在同一前表末至本表始的间隔内，从后向前找任一受支持的单位引言。因此，较早发行说明 `as follows (in millions)` 可跨过当前表说明，与当前caption明确的dollars冲突并造成误拦。

新代码先读所选表caption/前四行的显式单位。已经找到本表单位时，引言只查解析器得到的最后一个非空可见文字块，不跨当前说明回扫旧发行单位；没有本表单位时，仍走原来的有限回扫。`reporting_factors` 是原正则/倍率映射的提取复用。若caption、表头或紧邻且受支持的引言明确写不同倍率、外币词或已有外币符号，仍返回未决；后续可见数与行自身原生金额核对未改。

独立11项完整解析器base/patch对照全部符合预期，见 `base-patch-adjacency-controls.log`：

- 原 `prior_as_follows` ＋中间当前表说明＋dollars caption：精确base `UNRESOLVED`，patch `REPORTED_INCLUDED/追加0`。同样用头行给本表单位也得到此变化；较早明确euros跨中间块的情况得到相同有限修正。
- 紧邻millions引言与dollars caption、紧邻euros引言、独立 `(in millions)`、独立 `(in €)`：base和patch均未决。caption的millions与原生dollars金额冲突仍未决；邻接同单位继续通过。
- **缺本表单位的限制控制：**较早 `as follows (in millions)` ＋中间当前表说明且无caption/头行单位，base与patch仍未决。这证明本次没有宣称解决该旧范围限制；无表内单位且紧邻合法dollars引言仍保持原成功行为。

对照的base模块从指定Git blob在内存编译，复用现有完整primary/XML/native/table夹具；未落盘改写源码，不仅测试一个正则返回值。

## 实际执行与复用边界

1. 指定命令 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest tests.vnext.test_industrial_lease_relation -v`：**18/18通过，0.077秒，零失败/错误/skip**；进程墙钟0.407296秒，returncode0。见 `unit-tests.log`。未变用例随小套件运行，不扩大成旧全模块独审。
2. 指定命令 `PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-company-c02-venv-20261006/bin/python docs/evidence/issue28_b06_relations_20261008/verify_table_unit_scope.py /Users/lyuhongwang/Developer/SEC_metrics`：**returncode0**，脚本计时11.550370秒，进程墙钟11.889516秒。见 `saved-unit-scope-control.log`。
3. 保存Ford结构控制：原primary SHA `3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9`、旧Euro业务介绍派生SHA `8cbe0387ace33813443cbe4462e0869dfda89a4f773ca97dbad6f26db89dd40d`均确认包含/追加0；原明确€ caption反例SHA `74797e6c318a7f2015fde88d009b13d73386c57c3197f471f26e93c3f076bfde`仍未决/null追加额；较早billions＋当前caption millions的局部反例SHA `3dc1a200c42fb6fa3713c31b7437fb34def1a58c5ccf163e7c2d8090fdd62ea9`确认包含/追加0。table `table_000136`、插入位置4511248与已读父方JSON一致，没有换掉原反例。派生只在内存，不写回原件、不授获取信用。
4. 默认/JSON保存职责仅复用已读 `adjacent-table-unit-default.json`：父方记录default整个对象等于main8588、保存读取一致；本代理没有重新长演练或把它记成独立动态验证，也没有把父方selected case身份当作本次重新生成的身份。

以上正向仅是工业租赁包含关系，仍 `complete_B06=false/ratio=null`。工业权益和完整债务集合未建立；公司入口未消费该选项，没有新Run、公司CSV或完整B06结果。此次PASS不表示任意英文引言、任意版式或所有表前文本归属都已支持。

## 资源与操作

- 新spawn起始UTC：`2026-10-08T09:59:27Z`；首次实际时钟：`2026-10-08T10:00:02Z`；终检记录UTC：`2026-10-08T10:05:40.476488+00:00`；本次墙钟 **373.476秒**，截止 `2026-10-08T11:29:27Z`，未触90分钟。
- 本次 **35工具**（10次functions.exec、22次exec_command、2次clock、1次write_stdin；包含本结论写入工具），**1普通消息**（此后唯一最终报告）；问题/过程消息/spawn均0。未触80工具/3消息上限。没有继承旧代理累计或重置旧记录。
- 只执行上述两个指定短验证各一次、一个11控制短对照；没有完整公司/默认/JSON长演练。新增provider/paid/SEC/账户请求各0，无#47工作树/账本/运行根操作，无源码、测试、旧原件/旧资料编辑，无commit/push或tar。
- 本次只写本目录一个conclusion及必要日志。开工已有的旧conclusion修改和资源停止日志按原样保留；已读README、旧结论、全部 `adjacent-table-unit-*` bytes与开工快照相同。

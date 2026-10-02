# E01 布局后继精确增量限定独审

结论：**PASS_LIMITED；本次指定增量范围未发现新增 P1/P2。** 已登记的“仍占布局但不可见的块被当作移出布局”的函数级反例修复，正文结束边界与漏列 guard 共同使用同块可见引用算法。此结论只覆盖新显式 V3 来源输入，不授并购判断、公司完整 E01、Result/Run、390 或生产信用。

- patch SHA：`8ea442a38b87655c108dccec17b297ec11ff3d54`；parent SHA：`9a6dea271722b21f1f0145b502d14203332276bd`。
- 纯源码出处：只读 Git 对象 `9caada4ed62d02321d32fbb8249407b992de7154:scripts/vnext/historical_event_items.py`，从 `RULE =` 至 `def _primary_bytes` 前的范围与本方 reader 后半段逐字节一致，SHA-256 `3b719d2dda138f2bbcb13097b0ed446fd685c9521890e033319234e2d7a60929`。未导入历史路由/确认登记/Result 函数。
- 阅读当前 AGENTS.md 及实时只读 Issue #28，协作版本 COLLAB-28-47-v1.1。旧 `0de97ec9e280e578c809320c6c18c65381070f99` 限定结论复用其已闭范围；同时亲测 `peer-layout-control.json` 已登记的三个布局控制，未忽略该反例。未 fetch。

## 工程覆盖

`e01_item_text_28_v2.py` 分别保存“不可见”与“移出布局”状态。display:none、hidden、不显示元素及移出布局的祖先不制造块边界；visibility:hidden/opacity 等仍占布局的块制造边界。引用前文只取同块可见文字的最后 40 字符，大小写统一；br 不制造块边界。新 guard 直接调用同一 reader 的 `headed_item_codes`，新 V3 adapter 的正文也调用该 reader。

亲测原 laid_out_hidden_block 控制：旧 V1 guard 仍接受空头文件，新 guard 保留真正 2.01 并具名拒绝漏列；移出布局的内联节点继续排除同块 SEE 引用，独立可见段落仍识别真实标题。另选 11 个有限控制（含继承拒绝控制），覆盖不可见内联/块、移出布局父级、长隐藏节点、跨 br/内联引用、不可见 SEE、前段 OR、正文结束于真实下一条目或 SIGNATURES。三个正文边界控制分别核对了 guard 标题集、空头文件拒绝、正文返回和后继条目范围，全部符合预期。

第一次自选脚本在“正文包含非空 display:none 文字”时误期望返回正文，脚本 exit 1；reader 实际沿继承政策保守拒绝。原执行片段与失败说明保存于 `layout-controls.log` / `layout-controls-first-failure.log`。随后先验证新旧 reader 都拒绝该结构，再用空隐藏块单独核对布局和结束边界，`layout-controls-completed.log` **14/14 通过（3 个已登记开发回归、11 个自选有限控制）**。没有改源代码、测试或放宽断言；这些合成控制不声称实际财报出现该结构，也不冒充留出财报材料。

V3 adapter 与旧 V2 的差异只在版本标识、reader/guard imports 和所绑定文件名。实际源字节/长度、公司/申报/来源角色、全部发现申报的头文件 claim 集、当前或已登记前身事件窗口、修订证明及 source admission 检查继续复用原路径。条目 input ID 绑定原 claim/来源和正文，整体 input ID 另绑定 V3、三模块身份及全部来源/检查；`verify_current_e01_item_text` 要求完整重建相等，旧 V2 对象不能作为 V3 接受。输入仍明确 NOT_PERFORMED / NOT_CREATED、无 Result、零调用和无生产权限。

独立核对 **12 个旧 reader/guard/adapter、来源依赖、默认 Run、事件目录、active 和 AGENTS 文件**在 parent/patch/worktree 逐字节相同；新模块没有默认生产 caller。config 和 V13 decision 只追加三条 rule_paths，既有 flags/预算/冻结政策不变；V13/V14 对四个改变的执行文件身份相符，V13 new_rule_files 与实际规则集合相符。V14 引用 V13 全五文件身份相符，transfer 父闭包同步，三收据只改变 execution/requirement 身份字段，没有扩大许可。

独立按未改 engine 的五文件算法重算：

- V13 closure：`sha256:7644b72b80a1a316bc04c3cd9bc486510d779adb844777e63c59d8d39ed424de`。
- V14 closure：`sha256:367c186100561726d28025fa1fa97a531835912b5e4e1618498f3eb38e0be3ab`。
- V14 execution authority：`sha256:93ff5367240cf31d4b40476c64ff45619d8edcf6873d931d0b60cb093239c12d`。

三值与既有绑定记录和三收据相符。此次没有完整 Requirement loader 重放；完整 loader/semantic/wiring 通过及首次遗漏 rule_paths 被拒是仅读既有执行日志的证据。旧冻结版本/旧 Run/Result 没有重签。

## 亲测与仅读证据

亲自执行指定命令：

```sh
PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_e01_layout_successor.E01LayoutSuccessorFastTest
```

**4 项，0.001 秒，exit 0**；另有上述有限内存控制和静态身份检查。测试前后核对 10 个关键文件与 exact patch、提交方 tested-tree 的 SHA/长度一致；提交方原材料测试发生于提交前未提交树，此处仅证明关键字节等价，不改写其执行时间身份。

材料、全 fast、安装/异进程 cold 均**只读已有脚本/日志与盘上保存文件，没有重跑**。既有材料 1/1、12.566 秒；无公司硬编码源码检查 1/1、11.199 秒；全 fast 150 入口、56.78 秒、0 失败（FAST_LOCAL_ONLY）；安装两家公司 36.828 秒，Enphase 6 份检查/0 候选、Pfizer 9 份/3 候选；异进程 cold 14.606/16.560 秒。保存 cold 的 input ID、候选/检查数量与安装记录一致。

另独立只读盘比较两个安装根：各 **400 个 V13 execution 文件**均与绑定及当前 exact patch 字节相同；安装根的 V13/V14 各五文件也相同，三新模块在安装记录的哈希相符。安装/cold 脚本确实从独立进程加载各自安装路径并做原件输入重建；禁网、禁 116 旧语义导出、claims/来源日志/active 前后不变仍是原执行日志的限定声明，本次没有重新验证整份原件内容或再次执行 cold。

## 限制与资源

未覆盖：并购语义、计数/去重、完整召回、任意 HTML/CSS/浏览器排版、十家公司全部材料、已冻结旧 E01 新口径接受、新 Run/Result、390、材料/native/cold/全 fast 重跑、完整 Requirement loader 认证、真实 provider/paid/SEC、生产/active，及本提交其他执行状态工作。正文存在非空不可见节点时的保守拒绝仍可能降低自动完成率，这是继承边界，不由本次有限布局修复解除。只授指定增量工程信用；同族子代理检查不冒充独立人工验收、用户采纳或 GitHub APPROVE。

开始 UTC：`2026-10-02T19:30:34Z`。
结束 UTC：`2026-10-02T19:38:53.161344+00:00`。

工具共 **31**：外层 functions.exec **13**；嵌套 exec_command **17**、clock__curr_time **1**。普通消息 **3**（2 条 commentary、1 份最终报告），问题 **0**。未达 80 工具/90 分钟上限；新增真实调用 **0/0/0**。

只在本目录写 conclusion.md 与日志；未开发、spawn、commit、push、fetch、tar、账户操作或真实业务请求；未修改产品、#47/#54 工作树、分支、快照、账本或运行状态。父方已有 execution-state.json 修改仅记录，未处理。

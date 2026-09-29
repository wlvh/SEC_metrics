# `80322de9` E01 Item 8.01 来源修补限定独立审阅

**结论：NEEDS_FIX。** 本轮补丁修复了前次审阅的直接样例：普通正文中的 9.01 和 `SIGNATURES` 引用不再截断同结构标题之间的 8.01 正文；`script`、`hidden`、`display:none` 等内容不再伪造可见标题，出现 `<style>` 时拒绝。保存的 Southwest 正例仍能从原始字节重建。但是，下面两个独立反例仍能产出标称完整、可见的 `E01_VERIFIED_PRIMARY_ITEM_801_SECTION_V1` 记录。不能据此授予后继 E01 内容判断完整来源信用。

审阅对象为精确父提交 `7d0f7a69c202c0caf58d54e4a2785e1fa1c36ad9` 到补丁 `80322de9bfe171245c2d37bdff43c370321ea418`，限定于 `scripts/vnext/e01_item_source.py`、`tests/vnext/test_e01_item_source.py`、`repair-summary.md`。审阅时 HEAD 等于目标提交，三份受审文件的工作树内容与该提交相同；其他工作树变动未参与判断。继承前次 `independent-review/conclusion.md` 的未变部分，不重新审计旧路由和历史字节。

## 需要修复的发现

1. **[P2] 不同标签结构的真实结束标题不能阻止加粗交叉引用误截断。** `e01_item_source.py:107-120` 只在与 8.01 开始标题相同的标签内寻找边界，而且只检查被选边界之前的异标签标题。独立构造有效 hdr claim、source-set manifest、`fy_8k_primary` SourceReference 和对应原文字节：`<p><strong>Item 8.01 Other Events</strong></p>` 后先有加粗 `<p>` 引用 9.01，再有“we signed an acquisition agreement”正文，最后才是实际 `<h2>Item 9.01 Financial Statements and Exhibits</h2>`。`bound_801_primary_section()` **接受**，保存重建也接受，但 `section_text` 仅为 `Item 8.01 Other Events See the exhibit discussion below:`，收购段落被静默丢弃。修补测试只覆盖引用和实际 9.01 同为 `<p><strong>` 的情况，因此没有抓到不同标签结构。须在选定边界之后检查竞争的结构标题；无法辨别引用与真实标题时拒绝，不能返回截短正文。

2. **[P2] 显式不可见的行内样式仍被计入可见正文。** `e01_item_source.py:43-49` 仅识别少数隐藏写法，`opacity:0.0` 未匹配 `opacity:0` 的正则。`<p style="opacity:0.0">Hidden acquisition assertion.</p>` 在有效 8.01/9.01 标题之间被接受，输出包含该不可见句子；`color:transparent` 亦如此。这不是样式表带来的未知条件，而是原件内明确的不可见样式。修补应覆盖这些等价写法，或在不能证明行内样式可见时拒绝。前次“隐藏 HTML 可被接受”的一般问题因此尚未完全关闭。

上述均为离线构造反例，不主张 Southwest 原件含有这些形态。相反，独立读取保存的 Southwest 8-K、原 Run claim 与 SourceReference 后重跑：原文字节哈希相符，claim ID 保留，`verify_bound_801_primary_section()` 精确重建同一记录，正文 174 字符并排除 9.01；这证明该**单一**保存正例未被误拦，不证明其他合法布局的召回率。真实 8.01 与 9.01 使用不同标签而没有同标签候选时会拒绝，当前属于有界布局限制；需要在扩大适用范围时另验。

指定短测独立重跑 **4/4 PASS**；绑定检查返回 `PASS_EXISTING_V14_AUTHORITY`、`new_module_runtime_authorized=false`。读取执行方 `repair-fast.log`：`FAST_LOCAL_ONLY`、142/142 selector 通过；本审阅没有重跑 fast。绑定和 diff 支持旧默认路线未改变，新模块仍未进入当前 V14 运行权威。`repair-summary.md` 中对已测正例和当前非生产状态的陈述与这些证据相符，但“交叉引用不能静默结束章节”“显式隐藏内容不能进入可见正文”的普遍表述仍被上述反例推翻。

本结论不判断 E01 业务定义、真实来源获取、公司 Result/Run、生产资格、完整 PR、Issue #28 总体验收或跨原件召回；没有操作 #47/PR52、账本、分支、提交、推送、真实调用或发布。复现命令与输出摘要见 `review.log`。

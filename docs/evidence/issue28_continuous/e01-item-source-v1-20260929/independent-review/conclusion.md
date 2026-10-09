# `7d0f7a69` E01 Item 8.01 来源组件限定独立审阅

**结论：NEEDS_FIX。** 这次补丁保持了既有默认路线和 V13/V14 冻结文件的字节，来源与旧 claim 的标识关联、原文字节哈希、保存记录重建检查在已测范围内成立。但新组件会把正文中的交叉引用误当章节结束，也会把 HTML 隐藏内容当作可见章节。两种情况都会返回一个标为 `E01_VERIFIED_PRIMARY_ITEM_801_SECTION_V1` 的记录，故目前不能把其“完整规范化可见 Item 8.01 正文”承诺交给后继内容判断。

审阅对象为父提交 `237c7cf4c949a9c58bf857cd406e41ad6ec237d0` 到精确补丁 `7d0f7a69c202c0caf58d54e4a2785e1fa1c36ad9`。检查范围仅为 `scripts/vnext/e01_item_source.py`、`tests/vnext/test_e01_item_source.py`、`tools/run_fast_tests_v2.py` 的末尾 selector 与本证据目录。当前 HEAD 等于受审 SHA；三份受审源码文件的工作树 blob 与该提交一致。

## 需要修复的发现

1. **[P2] 正文里的 `Item 9.01` 交叉引用可被误认作真实章节结束。** `e01_item_source.py:30-43` 在压平的全文中搜索第一次 `Item 9.01 Financial Statements and Exhibits`，没有判断它是不是标题。构造一份有真实 8.01 和 9.01 标题的 8-K：8.01 第一段为“see Item 9.01 Financial Statements and Exhibits below”，下一段为“We signed an acquisition agreement”。通过既有 hdr claim、SourceReference、原文字节及完整 source-set manifest 调用 `bound_801_primary_section()`，函数**接受**，返回的 `section_text` 仅为 `Item 8.01 Other Events For related documents see`，将后面的收购段落静默丢掉。`tests/vnext/test_e01_item_source.py:115-120` 只覆盖其他 Item 编号的交叉引用拒绝，没有覆盖被选为边界的 9.01 自身。同理，正文中大写 `SIGNATURES` 会在 `:34-36` 被误作边界。修复需利用原件的段落/标题结构证明结束位置；无法区分时拒绝，不能返回截短的“完整章节”。

2. **[P2] 隐藏 HTML 可被接受为“可见正文”。** `e01_item_source.py:22` 直接复用 `_visible_text()`；该旧 helper 的 `HTMLParser.handle_data()` 收集所有文本，包括 `<script>`、`<style>` 和 `style="display:none"` 元素，未验证可见性。用已绑定的 hdr claim、SourceReference 与原文字节构造一份**只有隐藏 div** 含 `Item 8.01 Other Events` 和 `Item 9.01 Financial Statements and Exhibits`、可见段落没有 8.01 标题的文档，`bound_801_primary_section()` 仍接受并产出 `Item 8.01 Other Events. Hidden words.`。单独以 script/style 放置这些文字也能使提取器接受。原文字节哈希正确不能补上“可见”的证明。修复需排除非展示内容，或对无法确认可见性的输入拒绝；新增对应反例测试。

以上均为独立构造的离线反例，**不表示已证明保存的 Southwest 原件存在这些文本形态**；它们证明当前通用实现与 README 的完整性、可见性描述不符。补丁仍为 opt-in，现有 V14 运行权威未包含新模块，因此没有观察到当前正式 E01 结果被改变。两个问题应在新组件被接入后继 E01 内容判断前修复和复审。

## 通过的限定检查及证据边界

- `bound_801_primary_section()` 保留旧 claim 的 `verified_claim_id`，核对其中的 `primary_source_reference_id`、公司及 accession 与主文 SourceReference 一致，要求 `fy_8k_primary`，并用 `raw_asset_id` 核对传入的原文字节。`verify_bound_801_primary_section()` 从所给原件重建整个 dict 再做精确相等比较；当前定向测试覆盖正文篡改、错 claim、错原文字节。这里验证的是**所给记录之间的一致性**，没有独立重做 SEC 获取或证明传入 claim 属于某次真实采集。
- 独立重跑定向 `unittest`：**2/2 通过**；独立重跑只读 `check-binding.py`：`PASS_EXISTING_V14_AUTHORITY`，且 `new_module_runtime_authorized=false`。精确提交 diff 显示 `deterministic_router.py`、`normal_zero_ai_results.py`、`catalog/event_routes.json`、V13/V14 baseline manifest 均未改变，fast runner 仅增加一个末尾 selector。
- 已读取执行方保存的 `fast.log` JSON：`FAST_LOCAL_ONLY`、`PASSED`、142/142 selector、0 个返回码失败，新 selector 内 2 个测试通过；**本审阅未重跑全套 fast**。`README.md` 中 Southwest 保存原件的 174 字符正例与源审计属于执行方记录，本审阅未以其推断跨原件召回或业务正确性。
- 本结论不判断 E01 业务定义、真实调用、公司 Result/Run、生产资格、完整 PR 或 Issue #28 验收；未操作 #47/PR52、账本、分支或发布动作。

复现命令与最小输入/输出见 `review.log`。

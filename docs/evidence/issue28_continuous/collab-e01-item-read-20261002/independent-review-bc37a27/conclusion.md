# bc37a277 限定独立审阅结论（2026-10-02）

审阅对象为 `bc37a2779c4b687073594b0155cf84e7a5774711` 中 `scripts/vnext/e01_item_source.py`、`tests/vnext/test_e01_item_source.py`，以及 `collab-e01-pfizer-20261002/audit.json` 和 `collab-e01-item-read-20261002/` 的增量。**结论：Pfizer 已保存 8-K 的 8.01 正文读取与来源字节绑定成立；通用读取器有两处可复现的错误接纳，不能按当前代码认定目录排除和 Item 边界、可见性保护已通过。**以下反例是离线合成 HTML，不是 Pfizer 原件中的问题。

## 需修复的发现

1. **[P1] 链接目录仍可冒充 8.01，带链接的 9.01 标题又会被忽略，导致跨 Item 取文。** `handle_starttag` 只把新 `<a href>` 的 `linked` 标志写给当时已有的祖先，没有传给随后进入的子标题（`e01_item_source.py:85-92`）；标题搜集又直接跳过 `linked` 块（`:127-139`）。因此 `<a href="#i801"><h2>Item 8.01 Other Events</h2></a><p>Directory, not body.</p><a href="#i901"><h2>Item 9.01 Financial Statements and Exhibits</h2></a>` 被接纳，返回 `Item 8.01 Other Events Directory, not body.`。反过来，实际 8.01 后的 `<h2><a href="#exhibits">Item 9.01 Financial Statements and Exhibits</a></h2>` 被跳过，后面的 `SIGNATURES` 被选为终点，返回节段包含 `Item 9.01 ... Exhibit item should be excluded.`。新增测试只覆盖 `<h2><a href>8.01</a></h2>`，没有覆盖包裹标题的 `<a>`，也没有检查带链接的后续 Item 标题。建议传播祖先链接状态；无论标题是否可作为起点，只要可能是后续 Item 边界，就应先识别并在无法证明时拒绝，不能静默越过。

2. **[P1] 放宽 `position` 后，视窗外文字仍被当成可见正文。** `_visibility_uncertain`（`:28-54`）只检查 `left/top/text-indent/margin-left/margin-top` 中小于等于 `-999` 的偏移，不检查 `right/bottom`，也不检查很大的正偏移；`position:absolute/fixed` 本身已不再触发不确定。`<p style="position:absolute;right:-1200px">Invisible acquisition assertion.</p>` 和 `position:fixed;bottom:-1200px` 均被 `_visible_801_section` 接纳，返回的 8.01 文字含该句。现有测试只有 `left:-1200px` 负例。Pfizer 原件除普通 `color:#000000` 外，确有几处 `position:absolute;bottom:0`，但它们只包住空白换行。修复时应区分这种无文字占位元素与承载正文的视窗外元素；直接全局拒绝所有绝对定位会误拦 Pfizer 正例。

上述两个问题都在显式来源准备组件中，尚未进入普通 E01 Run；因此这是后续来源可靠性阻断，不代表本提交已经制造新的生产 Result。

## 已核实的正向范围与证据边界

- 从旧 Pfizer E01 Run 的 `DETERMINISTIC_VERIFIED_CLAIM`（8.01、accession `0000078003-25-000159`）追到 `SOURCE_REFERENCE` `sha256:1a47848c3657589557d8c1e8ffa667f839f38670ec0f80459e7dc4fdb424ab40`，再到原件 `sha256:7c006c40f40cafebc70a0b397d2da2603a1cb3fb5fe2a31a27fb0eca96296f2e`；本地实算 SHA-256 一致，SourceReference 指向 SEC Archives 的 `pfe-20251113.htm`。原件 UTF-8 无替换字符；读取器在原件中识别唯一 `div` 标题 `Item 8.01 Results of Other Events`，以同层 `SIGNATURES` 为界，正文长度 1423 字符，含 Pfizer 完成 Metsera 收购和合并协议，不含后续签名内容。独立重算 `section_id=sha256:8458bfb36890ae178463cd166ff4161925619a44429e92818ef94fdcf54d08d4`，与 `pfizer-section.json` 一致，`verify_bound_801_primary_section` 回放相等。这个认证证明**与旧 Run 保存的原件和身份一致**；本审阅未进行新的 SEC 在线获取。
- `audit.json` 的精确旧 Result 为 `sha256:277086505f0eac3cc0367f60ed7341785fb1fc7600ba5bbb952f0130e9fab0d1`，值 `0`；旧 claim 的 brief 是程序生成的 `8-K item 8.01 parsed from hdr.sgml`。该证据支持“旧零值遗漏相关正文”，不支持直接填写新的 E01 数值或完整公司计数。`pfizer-section.json` 也明确 `metric_result_created=false`、`current_390_credit=false`。本提交差异未改冻结匹配器、V13/V14 要求文件或旧 Result；缺陷登记仍扣留此精确身份且未释放。
- 在精确提交树运行 `PYTHONPATH=scripts:. /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_e01_item_source -q`：**6 tests，OK**。另用只读短脚本复现上面三种错误接纳。保存的 `fast-suite.json` 记载 145 个选择器通过，但其运行始于最终链接保护加入之前；不能称为最终树完整 fast 的独立通过。此次未重跑长材料、未发起业务调用，也未审阅 #47/PR52。

审阅仅覆盖上述增量和可访问的旧 Pfizer 保存材料；没有给予 E01 业务含义确认、十家公司召回、V13/V14 接线、原生 Run 或生产采纳信用。

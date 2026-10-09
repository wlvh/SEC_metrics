# 2d288bc 限定独立审阅结论（2026-10-02）

审阅固定提交 `2d288bc31aa076df6388f0b87a0d7bd961d1db54` 相对父提交的新增差异：`scripts/vnext/e01_item_source.py`、`tests/vnext/test_e01_item_source.py` 和本轮 `collab-e01-item-boundary-20261002/` 证据。继承 [bc37a277 首审](../../collab-e01-item-read-20261002/independent-review-bc37a27/conclusion.md) 对 Pfizer 保存原件的正向确认及两项 P1 反例；不重判首审已覆盖的全部代码。**限定结论：两项 P1 在本补丁的显式来源读取范围内已修复，新增差异可接受。**这不是 E01 内容判定、数值、正常 Run、390 项验收或生产采纳结论。

1. **链接目录与后续 Item 边界。** 新代码把祖先 `<a href>` 的 `linked` 状态传入子标题；带链接的 8.01 不再作为正文起点。标题收集仍保留带链接的后续 Item，若它是最近边界，读取器报 `ITEM_801_BOUNDARY_AMBIGUOUS`，不会继续越过 9.01 取到签名。定向测试的 `<h2><a>`、`<a><h2>` 两种顺序均被拒；我另以 `<a><div><h2>` 的目录、跨标签的带链接 9.01 和普通签名终点做只读反例，均按预期拒绝。
2. **移出视窗文字。** 偏移检查现覆盖 left/right/top/bottom、text-indent 和四向 margin，并对带符号数值取绝对值。`right:-1200px`、`bottom:-1200px`、`top:+1200px`、`margin-right:1200px` 的合成正文均报 `VISIBILITY_UNPROVEN`；普通正文及 `position:absolute;bottom:0` 的空白占位仍可读。这验证了本次指定的大幅偏移反例；该数值规则本身不等于对任意 CSS 布局可见性的完整证明。
3. **Pfizer 原件及旧路径。** 从旧 E01 Run 的保存 claim、SourceReference、RAW_BLOB 离线重建并回放 Pfizer accession `0000078003-25-000159` 的 8.01，得到同一 `section_id` `sha256:8458bfb36890ae178463cd166ff4161925619a44429e92818ef94fdcf54d08d4`、正文 SHA-256 `4010a39ce8eeb99867fc040e717fe3be2c0d5892aaf031e650115c1faed7625c` 和 1423 字符；原件哈希、claim/reference 身份也与首审及本轮记录相同。提交差异没有改冻结 E01 匹配器、V13/V14 Requirement 或既有 Result；仓库内此组件的运行引用仍仅见测试和 fast 测试选择器，未接入普通 E01 Result 路径。

在该提交树运行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_e01_item_source -q`，**6 tests，OK**。执行方保存的最终树 `fast-suite.json` 显示 fast **145/145**、`FAST_LOCAL_ONLY`；本独审只读核对该记录，未重跑整套 fast。额外只读反例为链接目录 2 例、带链接 9.01 边界 2 例、大偏移 4 例拒绝及可见占位 1 例通过。未发起网络或真实业务调用，也未操作 #47/PR52。

后续 E01 仍需按自身路线验证其他公司 8.01 版式、交易内容与主体、去重、正常原生链及结果验收。Pfizer 旧零 Result 的扣留不因本次来源修复而解除。

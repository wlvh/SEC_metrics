# D04：完整输入文字阅读，整份申报接受仍有图像边界

本次是执行者对原 16 份付费回答的**事后阅读**，不替换调用前限定参照，
不声称独立人工审阅。原回答、Run、公共行、失败及封存运行包逐字不改。
新增 provider/paid/SEC 为 0/0/0，接受数仍 909，缺陷对象仍 104。

逐块读完 Marriott FY2023、FY2024 年报及 Paramount FY2024 年报和 10-K/A：
共 8,800 个完整 B 块，39 个不按关键词过滤的连续阅读包。原请求中的
4,782 个原生事实、175 个补充对象均有文字覆盖映射：按原源序连接的完整
B 文字覆盖非数值正文，只归一空白；不在其中的非数值内容另读，所有
concept/type 名称另读。数值和 context 的操作数只登记，没有进行全面流动性分析。
原始每一 B 块的字节跨度 SHA 都与认证原件相等。修订文件没有因声明
只补 Part III 而跳过。

`reader-notes.json` 保存每个完整包的具体阅读判断；早期工具截断的内容已补读，
不能用已调用工具替代已读到文字。`complete-text-two-direction-read.json` 固定
全部 16 个原请求、原答 SHA 和 74 个原单元：唯一输出仍是 Paramount B340 的
条件性流媒体盈利风险，当前合同的 TARGET_REGISTRANT 指其自身业务，不代表
母公司疑虑。正文到模型的另一方向没有发现新增必评候选或明确持续经营评估。
清洁审计意见、足够资金预期、酒店业主破产、养老金计划状态、资产减值、
交易融资条件、诉讼与网络安全的局部无重大影响判断均按实际主体和范围排除。

这只建立完整**供应文字范围**内的判断。四份 HTML 仍有 14 个未读图片引用，
图片字节不在原模型文字/原生输入内；alt 名称不能证明其内容或无关。
外部并入的、未在本固定原件集合内的资料也未冒充已读。因此整份申报各媒介
的语义接受仍为 NOT_PROVEN，没有加接受或将空值改成数值“无疑虑”。
三份原生结果继续 NONE/WITHHELD、value=null；旧完整性缺口没有改名成披露不足。

离线复现阅读包、映射和绑定核对（脚本不自动产生语义判断）：

```sh
python3 docs/evidence/issue47_history/d04-full-text-read-2026-10-04/prepare_full_read.py \
  --requests <原封存包 dump_requests.py 所得目录> \
  --source-root <已批准 SEC 导出 restore 所得 source-inputs 根> --out <新的空目录>
python3 docs/evidence/issue47_history/d04-full-text-read-2026-10-04/map_native_text.py --root <上述新目录>
python3 docs/evidence/issue47_history/d04-full-text-read-2026-10-04/build_report.py \
  --requests <同一请求目录> --reading-root <上述新目录> --out <新报告.json>
```

本轮另起目录完整重建，报告逐字节相同；`fresh-rebuild.json` 保存比较哈希。
新文字阅读可与原运行对照，但不是新 DeepSeek 验收、生产采纳或资源恢复。

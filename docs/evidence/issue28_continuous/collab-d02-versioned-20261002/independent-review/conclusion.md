# de22326d 限定独立审阅

审阅对象为 `de22326da963f83771241c0f6e968ed33b810f70` 相对 `fdeafd4365a918b36dcd7c65540f2ad7f597c89c` 的指定文件差异。结论：**本补丁的版本接线、已列原件正反例和私有 Run 保存／冷读在已检查范围内成立；D02 Item 8 通用排除规则有一个可复现的误删反例，因此不授予通用内容验收或当期结果信用。**这是规则风险，不是已确认的现有十家公司结果错误；现有真实原件中本次核对的四处排除均符合披露含义。

## 需修复的发现

**[P2] 单个逗号被当成列表，可能删除实际诉讼披露。**`catalog/r6/D02_item8_category_28_v1.json:8` 的 `separator_after` 接受任意紧接关键词的逗号，`scripts/vnext/d02_item8_category_28_v1.py:85-88` 就据此把关键词判为列表成员；`classify` 在没有列举的暴露词时排除整个段落。对明确表示本公司涉诉的 `We face litigation, which could result in a significant loss.`，当前函数返回 `category_mention=True`、`exposure=[]`、`left_out=True`；`Litigation, brought by a customer against us in 2025, remains unresolved.` 也返回 `left_out=True`。两句均是构造反例，不是声称源文件中出现了这些句子。它们证明“逗号之后”不足以认定“只是在列举类别”，并且 `face`／`brought ... against us` 不在当前保护词中。经 `ordinary_d02_item8_v1.select` 用于 Item 8 时，这类真实法律事项会从候选和后续 ReviewUnit 中消失。建议收紧列表的结构性证据，并把这种正向披露加入回归；只扩充暴露词难以穷尽表达方式。修复后按变化重验本次四处排除、保留例和新 Run 回读。

## 已核对的边界

- `text_results_v2.py` 和 `normal_run_v2.py` 在该提交均无差异；新 `d02_text_results_v3.py` 相对 V2 只增加显式 `d02_category_policy` 检查和对原提案的过滤调用。未选该政策时，现有定向测试核对 V2 与 V3 候选相等。新规则与词表相对固定的 #47 `104876d6` Git 对象只替换了本方版本化路径，没有直接导入对方开发模块。V13/V14 快照、父子 closure、执行绑定及三份现有接线收据通过只读校验。此项不授予下一次真实调用资格。
- 直接解析四份本方现有 10-K 原件，原始文件 SHA-256 与登记的 `raw_asset_id` 一致。Lumen Item 8 #1670 是法律顾问成本政策；Pfizer #2175 是估计风险列表、#2240 是应收款催收方法示例；Paramount #2257 是贷款 covenant 的 EBITDA 加回类别。四块被排除符合其完整段落含义。Paramount #2108 的 2023 年股东诉讼收益是实际事项，规则保留它；它在当期财报中的摘录不等于 2025 年发生该金额。Enphase Item 3 #755 是页脚，依然保留，现有 D02 错误身份不得解除。
- `run.json`、`cold.json` 的零真实调用、独立状态根、Lumen 15→14 和同一 Result 回读，与本地保存的 `manifest.json`、`terminal.json`、`current.json`、`records.jsonl`、两份公开行哈希一致。旧成功尝试在随后的 `NO_SOURCE_CONTENT_CHANGE` 尝试后仍被引用。源码中的通用 `_verify_candidate` 会重渲染并逐文件比对，失败／中断时保留先前成功指针；本次没有做破坏注错。已有 `PASS`、`PUBLISHED`、`EXACT` 只表明原生程序门通过，不证明 14 条内容完整正确。
- 指定测试的最终修正日志为 2/2 通过，旧失败日志保留；现有 fast 报告 146/146 通过。本次另外仅执行指定 `py_compile` 与只读核验，没有重跑耗时的 Run 演练。Pfizer、Paramount、Enphase 尚无本补丁的新私有 Run 内容验收。该过滤器只会减少旧关键词候选，不会补找未被关键词纳入的披露；这类漏项以及 Enphase 页脚仍须单独处理。

未改 #47/PR52 的工作树、账本或运行根；未发模型或 SEC 请求；未提交或推送。审阅执行记录见同目录 `review.log`。

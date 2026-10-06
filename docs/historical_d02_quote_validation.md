# 历史 D02 引文检查（H1）

本项按 [#47 H1/H2](https://github.com/wlvh/SEC_metrics/issues/47#history-simplification-20261006) 和 [#28 唯一共同规则](https://github.com/wlvh/SEC_metrics/issues/28#collab-28-47-v1) 交付小 PR。`scripts/vnext/legal_review_contract.py` 提供共用的请求构造、回答形状及引文检查；历史分支的 `historical_legal_review.py` 消费它，保留旧登记/读取。公共 AGENTS、runner 和 CI 由 #28 集成，本方提供这组短测试。

旧检查把字符串类型、逐字匹配和 20–300 字符长度合成一个布尔值，失败一律报“不是该块原文”。现在依次区分缺引用、非字符串、来自另一供应块、在目标块无原文匹配、过短和过长。先检查来源支持再检查长度，因此凭空生成的长句不会被报成“真实但过长”。匹配不修剪或规范化原文，字符计数继续使用原合同的 Python `len`；请求、提示、定义和长度上限不变。

保存回归夹具仅含必要材料：8 份原助手回答完整内容，以及回答中点名的原供应块；未点名块、完整请求和 wire 继续保存在 [PR52 原模型归档](https://github.com/wlvh/SEC_metrics/tree/be3660476fffd05329f6cb985a520fdc44ede58c/evidence/issue47_model_calls/9a368413797ddef1)。夹具是机械检查的测试投影，不能当作后继模型请求、法律内容参考或完整指标接受。8 份原回答中的 14 条过长引文都逐字出现在对应原块，长度为 302–496 字符；8 份仍失败，只将新检查的报因改为 `D02_REVIEW_QUOTE_TOO_LONG`。原模型回答、失败、Run 和固定执行包不修改，也不裁剪引文补成功。

主要验证：

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_legal_review_contract -v`：14 项通过，包含 8 份真实失败回答、全部 14 条过长引文和类型/错块/缺引用/边界/未决反例；一次读取夹具，不安装或重放整家公司。
- 从原归档读取全部 12 份 D02 请求，在内存重建并逐字节比较请求，全部相同；用原回答比较检查结果，4 份合同通过、8 份仍因长度失败。无新模型或 SEC 调用，无 Run 登记。
- 历史消费者的现有请求、回答形状和未决处理短测试 12 项通过；原消费者接口保留。没有重复两年 B01、全量历史计算或旧资格/防伪测试。

这份共用模块及历史适配尚待各自 PR 合入，不表示 main 的公司 CLI 已完成 D02 历史业务接入。这里修复报因，未改变法律范围判断或引文合同；Pfizer 税务误纳、Marriott 自保遗漏等内容缺陷仍在原队列。后续确需改变回答合同，应另列具体差异及受影响验证。

自动CI的fast作业[37474922205/job/112307725659](https://github.com/wlvh/SEC_metrics/actions/runs/37474922205/job/112307725659)已失败：119个既有入口中，`test_invalid_source_fiscal_label_and_cik_are_integrity_failures`和`test_registry_company_04`各达到原30秒时限（exit 124），不是D02业务断言失败。未改公共CI、放宽时限或手工全量重跑；公共测试分层由#28 T1接收，本地定向通过不写成整条CI通过。PR59另提供小DEI期间/主体反例。

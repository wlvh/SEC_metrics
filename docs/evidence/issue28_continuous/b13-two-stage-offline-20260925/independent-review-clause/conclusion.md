# B13 两阶段分句主体绑定：限定差异独审

- 审阅补丁：`f6be0934d8c2fc73cb3fbb3bdcb113a462135837`，相对 `79fe67b197c601d387fc9464f7a7ff3358fb65b3`。
- 范围：仅 `scripts/vnext/capacity_two_stage.py`、`tests/vnext/test_capacity_two_stage.py`、`requirements/issue_28_v14/baseline_manifest.json` 的此次差异；继承 `../independent-review-local/conclusion.md` 的已知 P2。没有复审双阶段长链、全 PR 或真实模型准确率。
- 结论：**NEEDS_FIX（P2，新增错误接受）**。补丁修复了指定的跨分句供应商误拦截，同时新增同一分句中“过去有产能，现今仍有产能”的错误排除通道。另一个同分句供应商反例说明主体绑定修补仍不完整；它在前驱中已存在，不算本补丁新引入。

## P2：只看第一处产能关系，漏掉同一分句的当前断言

完整可见块：

> Our contract manufacturers used to have production capacity for obsolete products and now have production capacity for current demand.

它同时明确陈述了过去的旧产品产能和现在的当前需求产能。扫描包含该块；第二阶段若把整个块标为 `other_context / OTHER_ENTITY / CURRENT_REPORT`，原 V4 验证器接受，`unresolved=[]`。补丁前的辅助判断为 `True`，会拒绝这个错误标签；补丁后判断为 `False`，`validate_interpretation()` 实际返回 `ACCEPTED`。最小复现输出见 `adversarial.log`。

直接原因是 `capacity_two_stage.py:90` 从 `physical.finditer()` 改为每分句仅 `physical.search()`，只检查第一处 `production capacity`。第一处前缀是 `used to have`，因此按历史关系跳过；同一分句第二处 `now have production capacity` 不再检查。`validate_interpretation()` 在 `:554-562` 仅依赖这个辅助判断来拒绝错误主体、时间和类别标签。修复应能逐条处理同一可见块内的产能断言，或在无法可靠绑定断言时保留未决；无需继续扩张通用英语词法规则。

## 已修复与仍有界的反例

- 指定的 `Our contract manufacturers previously had limited output; a supplier has manufacturing capacity for its own products.`：前驱辅助判断 `True`、补丁后 `False`；完整 V5 第二阶段的 `other_entity / OTHER_ENTITY / CURRENT_REPORT` 正确排除已接受，`unresolved=[]`。
- 紧邻明确承接的 `Our contract manufacturers previously had limited output; they have sufficient production capacity for anticipated demand.`：补丁后辅助判断仍为 `True`；错误 `other_context / OTHER_ENTITY / CURRENT_REPORT` 被拒绝。直接当前产能的错误主体与历史时间标签也由现有测试覆盖。
- 单独的 `used to have` 旧关系和 `If ... could have` 条件关系：补丁后辅助判断均为 `False`，本次完整 V5 隔离响应均可按其非当前类别接受。
- 尚存的同分句供应商误拦截：`Our contract manufacturers source parts from a supplier that has manufacturing capacity for its own products.` 中，产能明确属于供应商，但补丁仍从同一分句里的 `our contract manufacturers` 借用目标主体；正确 `other_entity / OTHER_ENTITY / CURRENT_REPORT` 被 `B13_TWO_STAGE_EXCLUDED_PHYSICAL_CAPACITY_REQUIRES_REVIEW` 拒绝。前驱也如此，故属于旧 P2 的未覆盖变体，不是新增回归。以上两种反例足以界定当前修补的边界，本独审未穷举英语表达。

## 核验边界

- 指定的三套短测实际运行 **31 项，通过**。`git diff --check` 通过；三份受审文件与指定补丁 SHA 在工作树中无差异。V14 manifest 两处绑定均为目标脚本实际 SHA-256 `3cc9778af80b5333d5dac545a7dd702827816d50ffe5771384d9619ddc7d4c6d`、`31174` 字节。
- 只读查看 `../stage3-clause-repair.log`：执行方记录原序号 3 的当前闭包重放 `CURRENT_V5_STAGE3_READ_ONLY_REPLAY_PASS`，新录制调用 0、真实调用 `[0,0,0]`。本独审没有重放该真实原件；这行日志不覆盖上述合成反例，也不证明真实模型会输出错误标签、整家公司完成或生产可用。
- 本独审仅用合成可见块在内存中走完整扫描、判断和原 V4 验证器，没有发 provider／SEC 请求、跑长链、commit/push、改账本或操作 #47／PR52。只写本目录的 `conclusion.md` 和 `adversarial.log`。

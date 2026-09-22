# 112—114 限定差异独立审阅

结论：在约定范围内未核实出新增阻断缺陷；限定差异审阅通过。此结论仅覆盖下面已检查的实现与反例，不是全 PR APPROVE，也不授予真实重发、Ready、合并、采纳、部署或 active 切换权限。

- Base：`842f221029b0f7737bcd882a1e4b46260ef24662`。
- Patch：`a87db7f5464a3b3856f2a4c23ec6b66845f08888`。
- 输入：委托中列出的 11 个差异路径、修复 README、原 calls/0111—0114，以及指定测试命令。没有读取其他任务状态，也没有审阅 Issue47/PR52。
- 11 个工作文件均逐字节核对为 patch 版本；范围内 12 处 baseline 文件绑定与实际 SHA256/大小一致。证据见 `difference-checks.log`。

## 核实结果

1. **113 的来源字符串完整性**：`_source_json` 与 HTTP `request_body` 对 B13/D04 采用不改动字符串的序列化，登记、导出和读取对应改用同一表示；历史 canonical 和业务摘要函数没有改动。指定测试覆盖分解 Unicode、希腊问号、欧姆符号以及 ASCII 字节兼容。直接读取原 113 时，来源内容与原单元摘要仍不一致，新检查器继续拒绝，未将损坏原件修成成功。将这个原 113 输入送入 `execute_d04_assessment`，它在进入账本方法前抛出 `CONTINUOUS_SOURCE_UNIT_SERIALIZATION_CHANGED`，账本调用为零；这实际验证了既有 40ca426 付费前 guard 的位置。
2. **114 的类别交集**：原响应在 base 检查器被 `D04_SOURCE_FACT_CLASSIFICATION_CONFLICT` 拒绝，在 patch 检查器得到一条发现、零未决。原文是供应商等伙伴继续投资其业务能力的风险条目，原响应类别为 `CONDITIONAL_OR_BOILERPLATE / OTHER_ENTITY / CONDITIONAL`。新增接受只在 `_specific_continuation_activity` 已证明具体活动时发生；该函数先排除含 doubt/going-concern 的语句。独立混合段落反例显示，独立成句的真实持续经营疑虑不能被该条件类别覆盖；分号、but 接续的未证明作用范围保持未决，并非证明未披露。
3. **112 的显式紧凑合同**：实际 111 与 112 请求转成 compact 后，除响应协议和请求 ID 外，所有原字段保持相等，包括来源分组、单元、正文、必评集合、提示及语义定义。compact 具有新业务摘要；V1 默认不变。实际 112 的清单区分正文 B1884—B2708、原生事实 F1—F451，不能将前缀错误自动改为另一种来源。原 112 仍是 `finish_reason=length`、输出 4096 tokens、无独立 assistant-output 文件；其截断正文中可读到 1 个超出本组类型/编号范围的完整引用片段，这只是截断文本检查，不是修复后的响应。
4. **原成功保持原义**：原 111 的原响应通过完整 B13 内容检查，5 条发现、零未决；重建的 HTTP 请求与原发送字节相等。只核实原响应在当前内容检查器的兼容性，没有新建 Evidence/Run、重签或给它增加整指标/生产信用。
5. **原件完整性**：审阅前后 66 个原件文件逐字节一致；0111—0114 的 terminal 中所列 evidence 文件摘要全部匹配。四个原请求从已保存 request JSON 重建的 HTTP 字节均与原发送字节相等；这不表示已损失 Unicode 的 113 原件已恢复。

## 测试和反例

指定命令已运行，exit 0，38 tests 通过（0.441 秒）：

```sh
PATH=/Library/Developer/CommandLineTools/usr/bin:$PATH PYTHONPATH=scripts:. /tmp/sec_metrics_ci_20260922_venv/bin/python -m unittest tests.vnext.test_capacity_reference_contract tests.vnext.test_native_unit_index tests.vnext.test_continuous_source_unit_bytes tests.vnext.test_d04_native_assessment
```

独立短检查另核实：compact 分组重建；缺失实际 111 的五项必评内容被拒；未审阅单元、重复单元、重复引用、越界补充对象归属被拒；D04 的真实疑虑/具体活动混合语句不能无条件得出“无疑虑”。分别见 `compact-counterexamples.log`、`counterexamples.log`、`preclaim-and-integrity.log`。

保留两次审阅脚本自身的错误预期：第一次把 `If …, and …` 的条件作用范围样例先验当成无条件疑虑，断言失败；复查语句与新旧解析结果后，未将它登记为已核实缺陷。第二次使用主动清空必评集合的 fixture 断言“空 findings 必须拒绝”，断言失败；改用原 111 的真实五项必评集合后得到预期拒绝。两次失败后尚未执行的检查没有计作通过，后续执行记录另存；不改写失败日志。

## 审阅边界与仍需满足的条件

本轮没有模型/SEC 调用，没有账本 claim，没有 commit/push，也没有修改生产入口。没有执行完整来源材料长测试、完整登记—导出—跨进程冷读链或最终 `validate_wiring_receipt`；对登记/导出/冷读的结论是差异代码核对，完整链证据由执行任务另行验收。没有证明 compact 实际模型输出必不超过 4096；格式容量不能代替真实结果。113 原材料已发生的信息损失不能从该损坏 JSON 自行恢复，重新从受信原件准备来源的正向材料不在本轮输入范围内。

原 111 的成功和 112—114 的失败保持原义；特别是 114 新检查器离线接受不改原 FAILED_TERMINAL，也不授予摘要不变的 113/114 重发权。真实调用仍须最终执行绑定及适用明确授权，不得凭本报告绕过。

## 执行计数

共 45 次工具调用（按更保守的计数，将 14 次 `functions.exec` 外层调度、29 次 `exec_command`、2 次 `write_stdin` 全部计入）；未使用子代理。共 2 条普通消息：一条开工说明、一份最终报告，无问题。用时约 20 分钟，低于 80 次工具调用 / 90 分钟 / 3 条消息上限。

写入仅限本 `independent-review/` 证据目录中的 conclusion.md 与日志；未打包归档。

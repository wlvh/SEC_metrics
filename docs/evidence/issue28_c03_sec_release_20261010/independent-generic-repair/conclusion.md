# 通用 PeoMember 修后限定独审：原 P2 可关闭

本次只审 `31b74980b936e89934023408e96573bdc392db5f → 8f1250bf7252720d422f8fcdc43c85d431b40dfc` 的两处通用成员判断与一项新增回归。工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-c03-release/SEC_metrics`。历史发现出处为 `../independent-review/conclusion.md` 的“季度及日期版 PeoMember 被当作另一名具体人员”。本次未重审已经覆盖的其他模块。

结论：原通用成员版本识别 P2 可关闭，限定增量未发现新的阻断问题。修复将候选金额中的成员集合与当前姓名中的成员集合统一交给同一个有限 SEC ECD 版本判断；年份、季度和日期版本的通用 `PeoMember` 不再被错误计为第二个具体人员。此结论只覆盖这项源码差异，不扩展为公司原件、来源真实性、消费者接线、生产或正式采纳的批准。

## 直接复现与修复证据

从 base 提交用 `git show` 取得原源码，在内存中原样执行，未改写旧实现或测试预期。复用原失败输入：无人员维度的 USD 100、通用 `ecd:PeoMember` 的 USD 100、一个 `ex:PersonAMember` 的 USD 100。原实现年份为 PASS/100，季度 `2022q4` 与日期 `2022-10-31` 均为 `C03_MULTIPLE_REPORTED_PEOPLE`/null；head 三种版本均为 PASS/100，且具体人员集合精确只含 PersonAMember。每项结果都完成从原始输入的完整 replay。

另用同一当前人员分别以通用成员和具体成员披露姓名，并用无人员维度的 USD 100 金额，独立命中第二处 `current_people` 集合判断。base 季度/日期仍误拦截，head 三种版本均成功。因此两处修改都有直接运行证据，未只依赖新增测试覆盖第一处。

新增的已提交回归原样接入 base resolver：季度及日期两个子测试实际失败，断言为预期 100 与实际 null；接回 head resolver 后同一测试的三个版本全部通过。测试预期没有改变，详见 `regression-before-after.log`。

## 负例、默认行为与重放

三种版本各执行六项负例，共18项：候选金额集合或当前姓名集合中出现两个具体人员，仍保留两个成员并拒绝；外国命名空间的 `PeoMember`，仍保留为具体成员并拒绝；通用成员的冲突金额仍为 `C03_MULTIPLE_REPORTED_AMOUNTS`；同一通用成员的冲突姓名仍为 `C03_TARGET_FACT_INVALID`。这些结果均为 null，零业务调用且无正式发布权限。六项正例与18项负例全部完成24次完整 replay。

八种输入×三种版本共24次默认调用，与 base 比较完整返回结构，或异常类型和消息，全部一致；其中年份版本形成的8份 base 默认结果，可由 head 默认 replay 完整重建，selection hash与旧记录形状一致，没有新增政策字段。默认季度/日期仍为 `C03_DEF14A_SOURCE_REQUIRED`。本次差异未修改命名空间辅助文件字节，也未修改 `replay_c03` 函数结构。

修复后的显式结果在具体人员集合、记录政策、结果数值或输入中的人员成员被改变时，四项控制均被 `C03_SOURCE_REPLAY_MISMATCH` 拒绝。完整证据见 `generic-repair-controls.log`。

## 指定测试与字节绑定

实际运行命令：

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_c03_sec_release tests.vnext.test_governance_signals tests.vnext.test_xbrl_namespace_policy
```

Python 3.14.7；33 tests，0 failures、0 errors、0 skips；0.079s，exit 0。日志为 `required-unittests.log`。这只记录本地指定测试，未查询或宣称 GitHub CI 状态。

开始与结束核对三个允许读取的文件均与 head 精确字节相等；最终 SHA-256：

- `scripts/vnext/governance_signals.py`：af071cf433cd8073bc09833a34440f2f07daf47663142f611ba5a165553dab1c
- `scripts/vnext/xbrl_namespace_policy.py`：951b4d41a2541e96c22d4ad8eb230d03c7ccbdcf0a999131b9ad602e05383f98
- `tests/vnext/test_c03_sec_release.py`：969ef9b5d4811f2a144d3d49420c82f929e45032d49b8c018a3cefa4a733f20d

## 执行边界与实际量

UTC 开始：2026-10-10 12:11:30 UTC。
UTC 结束：2026-10-10 12:15:16 UTC。
实际工具量：6次 functions.exec，12次嵌套 exec_command；保守相加18次。普通消息2条，含首次范围说明与最终报告。均低于80工具、90分钟、3条普通消息的硬上限，未触发停点，限定范围内无遗留未覆盖项。

只在本 `independent-generic-repair/` 目录写入一份 conclusion.md 与三份日志。未修改源码、测试或其他文件；未重读真实大原件，未查询网络、未作真实调用、未 spawn、未 commit/push、未打包、未读取 #47 目录或状态。历史审阅和旧失败材料保留。

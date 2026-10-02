# 0ccf536 门禁补丁限定独立增量审阅

对象：`0ccf536368c5be71e633f7f15b5a317d02ec8f99` 相对 `de22326da963f83771241c0f6e968ed33b810f70`，仅审本次指定的 D02 门禁、相关测试、V13/V14 绑定和同目录证据。**结论：门禁补丁在限定范围内通过；前次 `de22326` 对共用 D02 排除规则的 `NEEDS_FIX` 原样保留。**本结论只支持在规则修复前暂停显式 D02 后继的新 Run 和更新信用，不授予 D02 内容正确性、既有私有 Run 或生产结果信用。

`create_normal_run(d02_category=True)` 在准备输入和写 Run 前拒绝；内部 `_create_case_run` 对已带 `d02_category_policy` 的 case 再次拒绝。`ordinary_update_cycle.run_once(d02_category=True)` 在解析状态根和进入更新锁之前拒绝，因而既不能新建尝试，也不能经 `_recover` 或 `NO_SOURCE_CONTENT_CHANGE` 把先前私有成功指针重新报告为当前更新成功。指定短测在全新状态根验证了这三种公开调用结果，1/1 通过。同补丁的 `guard-existing` 记录在既有 Lumen 私有指针上返回 `UPDATE_BLOCKED`，未交还 `last_verified_candidate`；独立只读检查确认该指针当前哈希仍与记录一致，状态根只有原有两次尝试。原私有 Run 可以按当时安装的冻结字节重读，这只保留历史可追溯性。

这三处新增判断均以显式 `d02_category` 或 case 中的 `d02_category_policy` 为条件。旧默认 D02 的 `prepare_case`、旧 Run 回放路径和其它指标的正常创建路径无本次逻辑差异。先前定向材料对默认 D02 候选等于 V2 的核对仍适用于未改的准备代码；本次最终树的 fast 记录为 146 个选择项通过、退出码 0。该 fast 记录未列出 D02 新短测，因此本审阅另行运行指定单测。

绑定按 Git 对象字节独立核对：V13 `new_rule_files` 和 `execution_authority` 中两份改动源码的 SHA-256/size 均与 `0ccf536` 相符；V14 执行绑定相符，其父级 closure、父快照文件哈希及 transfer 的父 closure 随 V13 更新。相对 `de22326`，V13 只改这两份源码的 8 个哈希/大小叶值，V14 只改对应 4 值及父级 2 值，transfer 只改父级 closure。当前 V13/V14 加载、执行绑定、V14 语义绑定及三份接线收据的校验通过。门禁前、后 closure 分别记录，先前 Lumen Run 不被重称为门禁后创建。

剩余限制：`We face litigation, which could result in a significant loss.` 仍被共用分类器误判为可排除；本补丁没有修复选择规则。`guard-existing.py` 的 `new_result_or_attempt_created: false` 字段没有在脚本内逐项统计尝试目录；本审阅依据门禁的前置位置、返回结果和当前目录只读核对判断该结论，未重新运行长演练。未审最终 head CI、真实业务调用或生产采纳。

执行命令与原始结果见 `review.log`。未提交、推送或改动 #47/PR52 工作区、账本和运行根。

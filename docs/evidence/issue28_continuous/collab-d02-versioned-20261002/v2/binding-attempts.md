# 绑定脚本初次失败的执行输出摘录

这不是原始日志文件：当时脚本将输出重定向到 `binding.log`，后续运行覆盖了该文件。以下是本会话工具输出中已显示的诊断，供解释修复顺序，不替代最终 `binding-final.log` 与实际需求身份校验。

1. 首次在写入任何清单前尝试加载旧V13需求，而规则列表已加入v2路径，返回 `RequirementError: Normal successor rule set differs`。改为从此前已验证的E01绑定收据读取修前闭包，保留 `binding-before.json`。
2. 下一次父级通过，后继加载返回 `RequirementError: Continuous rule set differs`。原因是脚本把V13新规则同时误放入V14自身专属 `new_rule_files`；修正为仅更新V14执行文件集合及父级引用，V14专属规则集合保持其原政策定义。

最终绑定在 `binding-final.log` 返回 `PASS_D02_V2_EXPLICIT_BINDING`；其前的中间成功 `binding.log` 只对应包装器尚未拆分时的中间源码树。真实调用0/0/0。

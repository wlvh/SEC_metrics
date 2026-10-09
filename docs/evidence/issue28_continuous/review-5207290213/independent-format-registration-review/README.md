# 独立限定审阅：来源分组格式的登记与恢复

审阅者为本轮请求计数工程子任务；本次只审阅**根执行者编写、审阅者未实施**的 `capacity_assessment_input.py` 与 `capacity_run.py` 格式登记/恢复差异，以及两个对应原生Run测试中的格式攻击。计数器、分组工厂及其语义不在本报告的独立批准范围；不覆盖D03来源事实旧模块依赖，不代替或重启9月17日前受限旧Codex审阅。

## 限定结论

在本次明确范围和反例下，未发现阻断问题。`scope-files.json`记录两个运行文件的确切SHA；实际使用的复制包运行文件与当前被审运行文件字节一致。测试文件为静态检查，完整Run结果由根执行者的原生材料单列，不冒充本审阅者重新跑了全部Run。

1. 登记字段来自工厂拥有的完整来源，只在新来源确实含 `request_context_format` 时写入，并进入 `input_record_id` 哈希；旧记录不补空字段。
2. `prepare_case`只把导出字段当成有限格式选择提示。B13实际 `prepare_capacity_semantic_source` 和D04实际 `native_source` 都明确接收该字段；不改变来源原文、原收据或用户权限。
3. 提示没有取得来源或结果信用的捷径。随后原有私有登记/安装信任根、完整source_id、input_record_id、模式、Requirement、所有原请求及原接受记录继续重验；导出内容还必须与受信记录完整相等。没有字段的旧默认保持None；明确参数与已安装提示冲突时拒绝。
4. 根执行者原测试使用的 `unapproved-format` 主要证明不支持格式会在前门拒绝。本审阅补测删除已经批准的格式、显式null、保持批准格式但重签调用方修改的登记身份，避免把前门拒绝当成完整登记边界证明。

## 新进程复制包实测

使用完整D04新格式记录材料的**复制运行时**，与单独复制的数据目录。运行时保留其固定源包和受信导出；攻击只改变数据目录导出并重算 `input_record_id`。未修改原包、原运行时、真实账本、原响应或收据。禁止网络。

| 场景 | 结果 |
|---|---|
| 完整原导出自动恢复受支持格式，实际prepare_case重建来源并读取接受记录 | PASS |
| 删除新格式字段并重签 | `NATIVE_ASSESSMENT_CONTEXT_FORMAT_CHANGED` |
| 将新格式改为null并重签 | `NATIVE_ASSESSMENT_CONTEXT_FORMAT_CHANGED` |
| 不支持格式并重签 | `D04_NATIVE_CONTEXT_FORMAT_UNSUPPORTED` |
| 保持受支持格式，添加调用方元数据并重签输入身份 | `B13_REGISTERED_ASSESSMENT_INPUT_CHANGED` |
| 明确函数参数与已安装导出提示冲突 | `NATIVE_INSTALLED_CONTEXT_FORMAT_CONFLICT` |

上述动态实测验证安装运行时/数据目录的既有信任边界；私有`.git`登记选择分支通过代码追踪与根执行者原生登记测试核对，本报告没有把复制包无Git分支冒充私有journal动态实测。未新增真实调用或完整真实公司—指标结果。

## 留存与限制

- `review.py`、`portable-review.log`、`results.json`保留实际入口、结果和原包字节未变检查。
- 首次硬链接复制被既有SEC原件单链接守卫拒绝，已删除仅本审阅副本以恢复原包链接数，改普通复制；`hardlink-first-failure.log`原样保存。
- 第二次从当前源码导入旧包，因根执行者随后更新了开发Requirement接线路径，被原安装版本相等检查拒绝；`current-root-drift-failure.log`保留。最终新进程使用复制包自身运行时，未放松版本检查。
- 发现一个非阻断材料遗漏：两个Run测试新增了格式攻击，但summary的`negative_cases`列表仍只列此前两项；已向根执行者指出，应该按实际覆盖补齐。

本报告不是用户本人审阅、全PR批准、真实语义路线解禁、Ready或生产授权。

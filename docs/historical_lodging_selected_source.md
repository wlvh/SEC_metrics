# B10/B11 共用已选择来源读取（H3）

按 [#47 H3](https://github.com/wlvh/SEC_metrics/issues/47#history-simplification-20261006) 接续 H1，修改现有 `lodging_table_source.py`，没有另建公司 pipeline。`read_selected_lodging_source` 接收完整原件、已选择的公司/申报/DEI 期间、政策和已编译的两个指标定义。来源准备负责发行人、申报、年度区间和修订；该函数负责完整表格集、明确年份列、当地范围/期间/币种说明、地理脚注和原格位置。它不重复选择最新申报或解析 DEI，也不改全局政策或临时改写函数环境。

当期 `prepare_ordinary_lodging_case` 将已经准备的输入传给原有 `prepare_saved_lodging_source`，后者消费此共用函数，避免第二次准备相同公司。原 `inspect_lodging_table_source` 接口仍为未提供准备输入的旧调用者检查 DEI，再调用同一表格函数。历史分支的标准/旧年说明适配也改为显式传政策；只在标准说明未证明时尝试已批准的复数及可选逗号形式，其他拒绝条件保留。历史上游 DEI 准备尚有旧包装，未声称整条历史链都已退出。

主要验证：

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_selected_lodging_source -v`：14 项短测试通过（9 项小表格、5 项最小DEI期间/主体测试），0.059 秒；覆盖单位、范围、非自然年标签、年份列、脚注、当期/显式政策隔离、错来源/公司/期间、竞争表和截断，不安装整家公司。新增最小DEI测试实际进入期间/主体判断，供#28 T1将慢的业务反例留在定向集成、快速层用小输入覆盖。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_selected_lodging_saved_sources -v`：2 项定向完整原件测试通过，4.808 秒；共享读取 Marriott FY2023/FY2024/FY2025，分别为 B10 `0.692/0.698/0.693`、B11 `124.7/128.23/128.8 USD`，原表数 `66/67/68`、`table_000011`、年份表头及原格文字/位置保留。当期旧接口与显式函数返回相同完整组件。
- 实际当期消费者直接读取保存原件：B10 `0.693 ratio`、B11 `128.8 USD`，均 `EXACT`、`table_000011`；分别 2.642/1.878 秒。测试在表格适配层禁止再次准备公司，正常计算通过。只在内存生成原生计算记录，无 Run 保存或调用。
- 历史消费者已有旧年测试：FY2021/FY2022 的 B10 `0.513/0.64`、B11 `74.66/110.64 USD` 及 FY2025 当期对照通过；4 项完整原件/拒绝测试 7.482 秒，另 4 项说明形式短测试通过。未重跑两年 B01、全量历史批次或旧信任/资格流程。

新增功能在小 PR 与存量历史适配分支，尚未合入 main；本项完成共用表格函数与消费者接线验证，不代替公司任务固定版本/CSV 的后续接收或完整五年业务验收。已保存原件、原 Run 与固定程序不修改。本轮模型/SEC 新增调用均为 0，历史来源发现/补齐仍按 H4/H6 接入同一公司入口。

自动CI[37478482242](https://github.com/wlvh/SEC_metrics/actions/runs/37478482242)失败，已读具体Marriott旧安装/Run作业：在准备指标之前，V14祖先检查以`Normal successor rule bytes differ: scripts/vnext/lodging_table_source.py`拒绝本次现行源码。该作业没有进入新表格业务判断，不能称公司CI通过；本次保存原件/真实当期消费者通过仍按上述范围解释。公共新版runtime/CI接收由#28继续，不为本PR重封祖先、回写旧Run或放宽业务断言。

2026-10-07接续共用计算：新增`normal_lodging_results.calculate_selected_lodging_metric`，消费已选原表组件、实际年度输入、同一指标定义和行业规则，统一原文/格位置到观察值的绑定及Calculator。当期case与存量历史消费者实际调用同一函数，后者的重复绑定和计算块移除；历史上游选择/修订与旧Run读口仍各自保留，未搬入main。本函数不重选最新、不重复解析来源、不保存Run，也不暴露任意正则。指定来源的拒绝与计算器单位拒绝区分，计算器异常保持原类型。

新增5个短计算例和原14个短来源/DEI例，共19例0.079秒通过；wrong-unit首轮测试误预期WITHHELD，实际计算器原本抛错拒绝，修正的是断言并保留首轮失败。实际main基短分支的当期B10/B11经原case入口分别4.985/3.257秒通过；历史分支当期和指定FY2024共四项也进入同一函数，每项调用一次，FY2024为0.698 ratio/128.23 USD，期间及原格witness保留。只验证本次受影响消费者，原五年表格/旧年说明验证继续复用。详细输出在[本次主要计算记录](evidence/issue47_history/lodging-shared-calculation-2026-10-07/)。

历史侧已将原resolver输出薄适配为公共case的expected_records/results/compiled_specs/source_proofs及所选prepared_input，不重新准备或造新pipeline。实测该case进入公共纯投影仍被其无条件重选最新FY2025挡住，报ORDINARY_PROJECTION_FISCAL_LABEL_CHANGED；公共负责人负责修复这一接缝，本方未复制投影器。恢复目录原件齐全但旧来源准入要求trusted journal的失败也保留在记录中，不能标成缺原件后自动GET。公共保存writer及普通历史公司范围接线仍待，当前小PR不宣称完整公司/五年接受。

代码a0685346的[CI37522373390](https://github.com/wlvh/SEC_metrics/actions/runs/37522373390)已终态failure：快测作业、inherited source material和历史兼容作业success；多项公司作业仍在旧lodging_table_source字节绑定前拒绝，另一个独立更新例为UPDATES_PARTIAL/UPDATES_INCOMPLETE断言失败，尚未证明同因。作业状态和首个失败的原日志片段在主要记录的CI-a0685346文件；不将定向通过说成整个workflow绿灯，不为这些旧路径重签快照。

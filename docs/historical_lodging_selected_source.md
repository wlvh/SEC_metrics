# B10/B11 共用已选择来源读取（H3）

按 [#47 H3](https://github.com/wlvh/SEC_metrics/issues/47#history-simplification-20261006) 接续 H1，修改现有 `lodging_table_source.py`，没有另建公司 pipeline。`read_selected_lodging_source` 接收完整原件、已选择的公司/申报/DEI 期间、政策和已编译的两个指标定义。来源准备负责发行人、申报、年度区间和修订；该函数负责完整表格集、明确年份列、当地范围/期间/币种说明、地理脚注和原格位置。它不重复选择最新申报或解析 DEI，也不改全局政策或临时改写函数环境。

当期 `prepare_ordinary_lodging_case` 将已经准备的输入传给原有 `prepare_saved_lodging_source`，后者消费此共用函数，避免第二次准备相同公司。原 `inspect_lodging_table_source` 接口仍为未提供准备输入的旧调用者检查 DEI，再调用同一表格函数。历史分支的标准/旧年说明适配也改为显式传政策；只在标准说明未证明时尝试已批准的复数及可选逗号形式，其他拒绝条件保留。历史上游 DEI 准备尚有旧包装，未声称整条历史链都已退出。

主要验证：

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_selected_lodging_source -v`：9 项小表格业务测试通过，0.060 秒；覆盖单位、范围、非自然年标签、年份列、脚注、当期/显式政策隔离、错来源/公司/期间、竞争表和截断，不安装整家公司。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_selected_lodging_saved_sources -v`：2 项定向完整原件测试通过，4.808 秒；共享读取 Marriott FY2023/FY2024/FY2025，分别为 B10 `0.692/0.698/0.693`、B11 `124.7/128.23/128.8 USD`，原表数 `66/67/68`、`table_000011`、年份表头及原格文字/位置保留。当期旧接口与显式函数返回相同完整组件。
- 实际当期消费者直接读取保存原件：B10 `0.693 ratio`、B11 `128.8 USD`，均 `EXACT`、`table_000011`；分别 2.642/1.878 秒。测试在表格适配层禁止再次准备公司，正常计算通过。只在内存生成原生计算记录，无 Run 保存或调用。
- 历史消费者已有旧年测试：FY2021/FY2022 的 B10 `0.513/0.64`、B11 `74.66/110.64 USD` 及 FY2025 当期对照通过；4 项完整原件/拒绝测试 7.482 秒，另 4 项说明形式短测试通过。未重跑两年 B01、全量历史批次或旧信任/资格流程。

新增功能在小 PR 与存量历史适配分支，尚未合入 main；本项完成共用表格函数与消费者接线验证，不代替公司任务固定版本/CSV 的后续接收或完整五年业务验收。已保存原件、原 Run 与固定程序不修改。本轮模型/SEC 新增调用均为 0，历史来源发现/补齐仍按 H4/H6 接入同一公司入口。

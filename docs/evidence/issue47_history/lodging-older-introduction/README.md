# B10/B11：住宿统计表引言的旧写法（2026-09-30）

## 问题

全帧批次里 Marriott FY2021、FY2022 的 B10/B11 按名扣留 `HISTORICAL_LODGING_SOURCE_ROUTE_UNRESOLVED`。冻结的住宿表检查（`lodging_table_source`）找到了目标表 `table_000013`，并标它"看起来是同一个目标"（`plausible_same_target: true`），但以 `LODGING_TABLE_PERIOD_AND_OPERATING_INTRODUCTION_UNPROVEN` 拒绝。这张表前的引言句必须证明它说的是哪一年、哪个范围，而已批的引言模式是最新几年年报的原句：

- FY2023 起："The following **table presents** RevPAR, occupancy, and ADR statistics for comparable properties for 2023**, and** 2023 compared to 2022. Systemwide statistics include data from our franchised properties, in addition to our company-operated properties."
- FY2022："The following **tables present** … for 2022**, and** 2022 compared to 2021. …"
- FY2021："The following **tables present** … for 2021 **and** 2021 compared to 2020. …"

期间和范围说的是同一件事，只是单复数和一个逗号不同。所以资料是够的，是程序不认这两种写法。

## 先量

只把引言模式换成也接受这两种写法，其余检查都用冻结的，结果是：FY2021、FY2022 各自只剩一张候选表，其余冻结检查全部通过。FY2021 的 B10 = 0.513、B11 = 74.66，FY2022 的 B10 = 0.64、B11 = 110.64。FY2023–FY2025 由冻结检查本来就接受，值不变（0.692/124.7、0.698/128.23、0.693/128.8），与已接受的一致。

## 改动（`historical_lodging_results.py`，规则文件）

- 先跑冻结检查；只有当它以"没有唯一匹配表"拒绝、且理由里有引言未证明时，才用新模式把整份检查重跑一遍。冻结检查接受的年报一个字节都不变。
- 新模式由冻结模式经两处精确替换得到："table presents" 换成 "(?:table presents|tables present)"，年份后的 ", and" 换成 ",? and"。每处替换必须恰好命中一次，所以冻结模式将来变了会按名停下，而不是被意外放宽。
- 其余策略值不变。组件记录新策略的哈希（`policy_hash`），读者能看出是哪种写法放行的。

## 验证

- 用例 `tests/vnext/test_historical_lodging_introduction.py`（8 例，约 26 秒，saved-source 层）。FY2021、FY2022 从导出读：冻结检查（经历史路线的 DEI 视图）因引言拒绝，新检查各得一张表，值如上，策略哈希是新策略的。FY2025 从检出读：结果与冻结检查完全相同。别的拒绝原样抛出，新检查不被调用。新模式接受三种印出的写法，冻结模式只接受最新那种。另有六个必须拒绝的句子："tables presents"、"table present"、分号、别的物业范围、别的比较口径、错的年份。策略只差这一个模式，替换目标缺失时停下。原有的 `test_historical_lodging_results` 8 例照样通过。
- 注错 `injections.py` → `injections.json`：6 个，在隔离克隆里跑，全部由为它写的用例抓到。

## 不保证的

- 这是一家公司两年的写法。别的写法（其他酒店公司、更早年份）仍按冻结模式处理，不会被这里放宽。
- 值还没有独立阅读。

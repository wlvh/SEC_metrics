# 定向运行：2026-09-30 的两轮（闭包 `c25dfc81` 与 `8530710b`）

`collect.py` → `rounds.json`。驱动是 `../period-batch/frame_batch.py`，数据根是导出恢复的根，每个期间一个数据根，零调用。

## 第二轮（闭包 `c25dfc81`，运行树 = `5866cbc1` 加注册补丁）

全帧批次之后修好的四处：2022 年代理没有 inline XBRL 的 C02/C03（FY2021，读代理薪酬汇总表）、D02 附注导航、D04 单对象上限、住宿表引言旧写法。21 个位置：20 个冻结出公共行、另一进程冷读同一 run 与 result；Pfizer FY2022 的 D04 由程序缺口变为按名停在"等模型审阅"（`HISTORICAL_SEMANTIC_ASSESSMENT_NOT_REGISTERED:LIVE`）。

## 第三轮（闭包 `8530710b`，运行树 = `1f8cea3e` 加注册补丁）

加入 ECD 第一版命名空间的放宽（`../c03-first-ecd-release/`），同时把第二轮的位置在新闭包下重跑。28 个位置全部冻结出公共行、冷读一致。

- 第二轮与第三轮共有的 20 个位置：结果编号与值逐个相同。
- C03 FY2022/FY2023 由"未找到来源"变为发布：Enphase 16,627,977、Ford 20,996,146、Marriott 18,686,271（登记为缺陷撤回，见 ECD 目录）、Paramount 前身 32,046,006、Pfizer 33,017,453 / 21,562,064。Lumen FY2022 两位 CEO（`C03_MULTIPLE_REPORTED_AMOUNTS`）、Macy's FY2022 的代理按日历年标注（`C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND`）仍是具名答案。

## 之后的阅读

- C03：`tools/read_c03_across_proxies.py` 对第三轮的 11 个往年值读登记人每份已存代理，10 个被路线没读过的代理独立确认并接受；Marriott FY2022 因代理之间数字不同不接受。
- B10/B11：`tools/read_lodging_table.py` 在导出上读 Marriott FY2021、FY2022，4 个值全部 MATCH。
- 接受登记 196 → 210。

## 不主张

这是定向运行，不是这个闭包的全量帧；上面没提到的值（C02、D02 的往年文本）尚未独立阅读。

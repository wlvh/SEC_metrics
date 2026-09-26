# 定向重跑：闭包 `c7a49b98`（31 个 Run）

## 跑了什么、为什么只跑这些

`d5de1684` 的三处文本修复只影响 D01、D02，`4f1be8d4` 的 B13 路线只影响 B13。本轮在同一只读运行树、同一闭包下，四个进程并行跑了这三个指标：D01、D02 各 11 个已存原件的期间，B13 在其中定义范围之外的 9 个期间。**其余指标在这个闭包下没有重跑，本轮不是该闭包的全量验收**；30 指标批次仍是它自己闭包的证据，不改签、不混入。

## 执行字节

运行树与仓库 `HEAD` 的 minted manifest 只差 12 个叶子，全部是 6 个注册补丁文件（calculator、constraints、projector、records、requirement_profile、run_store）的 sha256 与 size；`new_rule_files` 一个不差。31 个 Run 记录的四个 Requirement 文件哈希全部等于运行树当前文件。

## 结果

- 31/31 冻结并产出公共行；每个 Run 都在独立进程冷读，运行编号、状态、值、质量、发布逐项相同；零新增调用。
- D02 与 30 指标批次逐份比对：只移动了修复前探针预测的两块——Enphase 的页脚（18→17）与 Lumen 的案件名 "Blum"（41→42），其余九份逐字节相同。探针见 `probe-before-the-repair.json`。
- D01 十一个值都是已读过的值：七个等于 30 指标批次已接受的值，Marriott 三个与 `d4cf2c3f` 下读过的修复结果 result_id 相同；Paramount 那一行由短空隙修复补全为整句。
- B13 九个都是定义范围之外的 `N_A_STRUCTURAL / TRAIT_NOT_APPLICABLE`。

## 内容接受与缺陷登记

- D01 11/11 通过。Paramount 新读一份（`content-acceptance/d01-paramount-repaired-read.json`）：阅读器对"强调在不超过两个字符的空隙后恢复"的行只标记，并同时给出前缀与跨空隙两种读法，由记录下来的逐行判断选择——阅读器若也内置路线的桥接规则，错误的规则会在两边同时错而通过。
- D02 8/11 通过。新接受 Enphase 17 条：它正是早先双向阅读判为披露的 17 块、同一顺序、只少了页脚。Lumen 与 Paramount 仍被关键词代理缺陷撤回，Pfizer 仍被关键词代理那两块撤回。
- 释放：Paramount 截断、Enphase 页脚对各自新结果；Marriott 三个与 Pfizer 超链接对同一 result_id 在新版本下各自点名。
- Pfizer 的"条目上限"缺陷此前只对 `1b6d9c87` 下的 92 条结果释放，于是覆盖表把这个在 96 条结果上早已修复的缺陷报成撤回理由（它在登记表里排在前面）。现对 96 条结果在两个版本下各自释放，报告的理由变成真正仍在起作用的关键词代理。
- 新登记 `D02_LUMEN_2025_UNDERLINED_CASE_LABEL_DROPPED`：此前 AGENTS.md 写过 "Blum 保持登记"，实际从未进入登记表，什么都没撤回——与 Pfizer 超链接 Item 3 是同一种失误。现登记并对新结果释放；Lumen 仍被关键词代理撤回。

## 不主张

本轮之外的位置；本闭包的全量帧；任何值在已登记阅读之外的业务内容。

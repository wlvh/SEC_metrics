# D01 最新年份：规格 v2 下的结果重新读（2026-09-30）

## 为什么要重读

D01 的规格由 v1 升到 v2 只改了条目上限（64 → 192，`historical_spec_revision` 机械证明其余逐字相同），但结果的身份随规格走，`spec_closure_hash` 变了。接受登记按"值 + 身份"匹配，所以 41 期间批次（闭包 `ed360ebc…`）里 12 个最新年份的 D01 结果虽然行数与内容和以前读过的完全一样，在覆盖表里却读作"接受与这个结果不符：spec_closure_hash"。这不是内容问题，但也不能靠改匹配规则放过去：接受绑定规格，正是为了让含义变了的结果不会继承旧的阅读。所以对批次的这 12 个结果重新读一遍。

## 怎么读的

`tools/read_d01_headings.py` 与以前同一读法，每个位置按它被读时的判断文件读（读取工具新增 `--position <公司>:<期末>=<判断文件>`，每行记下 `judgements_file`）：

- Enphase、Ford、Lumen、Macy's、Pfizer、Salesforce、Southwest 的最新年份：`heading-judgements-30-metric-batch.json`；
- Marriott 三年：`heading-judgements-repaired-marriott.json`（批次结果是下划线修复之后的）；
- Paramount FY2025：`heading-judgements-repaired-paramount.json`（短间隙修复之后）；
- Paramount 前身 FY2024：`heading-judgements-paramount-predecessor-2024.json`。

结果：`../../content-acceptance/d01-latest-years-read-batch.json`，12 个全部逐行一致（MATCH）。

## 登记

- 同一坐标在两个规格版本下各被读过：登记为两条接受，第二条的编号带 `_SPEC_<规格摘要前 8 位>`（`tools/build_acceptance_register.py` 的 `_differs_in_the_spec_only`）。只在规格不同、其余全部相同时才这样；值、申报、期间、单位任何一项不同仍按"两份阅读对同一坐标说法不一"停下。
- Marriott 三年与 Paramount FY2025 各有一条已修复并释放过的缺陷，释放点名的是旧版本的结果编号。`release_on_reading.py` 只在"缺陷已对某个结果释放过、这份阅读对该坐标读成 MATCH 并记下它核对的是这个结果、运行目录与行收据一致"时补一条释放，点名批次的结果与闭包；输出在 `released.json`。开放缺陷不经这里释放。

## 不保证的

- 这是对同一批申报、同一批判断的重读，不是新的业务判断；判断本身的局限见各判断文件。
- 批次里 Southwest FY2022、FY2023 的旧值仍撤回（它们是分页修复之前的值，修复后的结果在 `../page-split/`）。

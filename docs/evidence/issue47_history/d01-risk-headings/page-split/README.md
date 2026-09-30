# D01：跑过页脚的标题（2026-09-30）

## 怎么发现的

往年 D01 的三向阅读（`../../content-acceptance/d01-older-years-read-batch.json`，判断在 `../heading-judgements-41-period-batch.json`）读了 28 个没人读过的往年值：26 个逐行一致；Southwest FY2022、FY2023 的发布值里有半截标题。申报让三条风险因素标题跑过页脚：前半截结束一页，页码、下一页开头带链接的"Table of Contents"行和分页线之后，后半截以小写开头另起一块。冻结的标题选择器把每个整块加粗的块都当一个标题，于是 FY2022 的值有 33 行（其中 4 行是两条标题的两半），FY2023 有 29 行（其中 2 行）。

## 量出来的

- 对 41 份 D01 申报扫描"只含标题、不以句末标点结束、只隔页面装饰又接一行标题"的两行：5 对。3 对是上面的续接（后半截小写开头）；2 对是页脚的分类标签接下一页开头的标题（Enphase FY2025、Southwest FY2025），确实是两个标题。
- `measure.py` → `measured.json`：在 41 个批次 Run 各自的申报上，用加了合并与关掉合并的构建器各建一次文档，交给冻结的标题选择器：只有 Southwest FY2022（33→31）与 FY2023（29→28）移动，失去的正是半截行、得到的是完整标题；其余 39 份文档逐字节相同。

## 修复

`scripts/vnext/historical_text_emphasis.py` 的 `join_headings_split_across_a_page`（规则文件，只给 D01）。条件与做法见 `architecture.md`。独立读取器 `tools/read_d01_headings.py` 标记每一对这样的两行（不看下一行大小写），每对都要一条记录的判断（`ONE_HEADING_ACROSS_THE_PAGE` 或 `TWO_HEADINGS`）；在这个标记之前记录的阅读行，判断补记在它点名的判断文件里（Enphase FY2025、Southwest FY2025 各一对，都是两个标题）。

## 端到端（闭包 `e667d42c…`）

`collect_targeted.py` → `targeted-runs.json`：Southwest FY2022/FY2023 与两个对照（Southwest FY2024、Enphase FY2025），驱动 `../../period-batch/frame_batch.py`，数据根是导出恢复的根，零调用。修复后的两个结果由 `../../content-acceptance/d01-southwest-page-split-read.json` 读成一致，两条缺陷只对这两个结果与这个闭包释放；批次里发布过的旧值仍撤回。

## 用例与注错

`tests/vnext/test_historical_page_split_headings.py`（13 例）与 `tests/vnext/test_d01_byte_reading.py` 的 `AHeadingRunOverAPageIsReadOnlyThroughItsJudgementTest`。`source-records.json` 是四份申报在批次 Run 里的 SOURCE_REFERENCE、RAW_BLOB 记录与计算目标，用例据此从已存字节（检出或导出）重建文档，不需要批次。`injections.py` → `injections.json`：路线 8 个、读取器 3 个，在隔离克隆里跑。

## 不保证的

- 后半截以大写开头的续接（例如以专有名词开头）路线不合并；读取器会标记它，但要靠判断发现。
- 页面装饰只认页码与带链接的目录行，这是本语料量到的全部形状；别的页眉写法不会触发合并。

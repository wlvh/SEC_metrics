# saved-source 层耗时：一个平方级正则与反复解析（2026-10-01）

saved-source 层三片连续在 35 分钟上限被取消，到达的用例全部通过（见 `../ci-job-patch/`）。原因不是哪个用例坏了，是整层装不下。这次找到两处可以安全去掉的重复：一处是本 Issue 自己写的正则，回溯成本是平方级；另一处是同一份申报的 inline XBRL 在一个进程里被反复解析。两处都不改变任何答案，下面逐项给出证明。

## 1. 页码页脚规则的正则（规则文件，移动闭包）

`scripts/vnext/historical_text_results.py` 判断“带页码的页脚”时，原来用

    ^(?P<stem>.*?[A-Za-z].*?)[\s|\-–—]+(?P<page>\d{1,4})$

两个懒惰组遇到不以页码结尾的块，会把每一种切分都试一遍，几千字符的段落要走几百万步。剖析下 D02 修复用例的 721 秒里，约 500 秒花在这条规则上（`re.Pattern.match` 共 498 秒，几乎全部来自 `_numbered_page_footers`）。

改为从末尾读：`_page_numbered` 先找末尾 1–4 位数字前面那一串分隔符，词干就是这串分隔符之前的文本；词干里要有 ASCII 字母，且不能有换行。这正是旧模式能取到的最短词干：懒惰组让引擎先尝试最短的切分，而唯一能走到末尾的切分起点，就是那串分隔符的第一个字符。新增的后顾断言只让搜索从一串分隔符的开头起步，答案不变；没有它，4 万个分隔符组成的一串要 15 秒（实测），加上后约 1 毫秒。`_numbered_page_footers` 另外改成对每块只读一次，原来每个候选块的左右邻居都要重读。

**证明答案不变：**
- `tests/vnext/test_historical_page_numbered.py`（fast 层，7 例，约 1 秒）以旧模式为参照逐一比对：43 个边界字符串（换行在词干里、在分隔符里、在末尾；4 位与 5 位数字；Unicode 数字与空白；非 ASCII 字母），20,000 个从边界字母表随机生成的串，20,000 个“词干＋分隔符＋数字”形状的串；页脚集合在 4,000 份随机生成的文档与随机范围上逐份比对旧实现。另有两例守线性：53,000 字符的段落（旧模式实测 36 秒）与 4 万字符的分隔符串，限时 2 秒。
- `equivalence.py` → `equivalence.json`：在最终获取导出恢复的根上，对帧的 50 个期间各取 D02 准备，把已提交路线与修改后路线放在同一进程里比较。191,859 次逐块判读（每块的原文和合并空白后的文本，其中 12,138 次以页码结尾）**零差异**；49 份文档全文的页脚集合相同（共 1,566 个页脚）；50 个期间的 D02 与 D03 提案、检查范围、覆盖状态、Item 8 审阅池全部相同。Lumen FY2021 在两版下都在准备阶段以同一个具名理由停下（`HISTORICAL_TEXT_BOUNDARY_NAVIGATION_INCOMPLETE`），所以它的块没有参与逐块比较。D02 准备的总耗时从 1,280 秒降到 318 秒。

## 2. XBRL 解析复用块（非规则文件，不移动闭包）

`deterministic_router.parse_accession_xbrl_source` 用两个 HTML 解析器读整份 inline XBRL 文档，返回不可变对象（冻结的 dataclass，contexts 与 facts 是只读映射和元组）。它只读交给它的字节。冻结链路的几乎每一步都会对同一份申报再解析一次：年度期间、财年标签、权益重建、修订范围、文本文档、B06 的每种语法。

`scripts/vnext/historical_xbrl_parse.py` 的 `xbrl_parsed_once()` 块打开期间，按字节的 SHA-256 加长度为键，同一份字节只解析一次，之后返回同一个对象。不是 `bytes` 的参数照样交给冻结解析器、照样被拒；解析抛错的不记住；最多保留 32 份文档，最旧的先丢，丢了再要就重新解析。块外什么都不变。块会把本包里所有绑定（包括 `deterministic_router` 自身的）换掉，出块时放回，块内才导入的模块也放回；嵌套时沿用外层；另一个线程打开会被拒；解析器已被别人替换时拒绝打开。规则模块不打开它。打开它的有两处：批次脚本（`../period-batch/period_runs.py`，与推导缓存同受 `--memo` 控制，抽查冷读关掉推导缓存时它也一起关掉），以及下表这些测试模块（按模块打开）。

`tests/vnext/test_historical_xbrl_parse.py`（fast 层，11 例，约 2 秒）覆盖以下性质：同一字节只解析一次，结果与重新解析逐字段相同；等长而内容不同的两份字节是两份文档；拒绝照旧且不被记住；被丢弃的文档会重新解析；绑定在块内被换、块外放回、出错时也放回、块内导入的模块也放回；嵌套与线程的处理；还有一份已存 10-K 经 release-aware 视图读出的期间，块内与块外相同。

每个模块打开块之前，都用一次实验（在测试运行器外把解析器换成记忆版）数过解析次数，并确认没有用例给解析器打补丁或按调用次数断言：

| 模块 | 解析调用 → 实际解析 | 打开块后本机耗时（4 核、4–5 个重作业并行） |
|---|---|---|
| test_historical_debt_results | 356 → 17 | 251 秒 |
| test_historical_period_results | 153 → 8 | 139 秒 |
| test_historical_part_iii_admission | 122 → 4 | 119 秒 |
| test_historical_board_composition_filings | 121 → 20 | 152 秒 |
| test_historical_risk_headings | 101 → 10 | 118 秒 |
| test_historical_governance_results | 95 → 15 | 89 秒 |
| test_historical_event_window | 93 → 3 | 109 秒 |
| test_historical_semantic_routes | 90 → 4 | 239 秒 |
| test_historical_predecessor_periods | 89 → 5 | 100 秒 |
| test_historical_event_items | 68 → 10 | 145 秒 |
| test_historical_lodging_results | 49 → 4 | 86 秒 |
| test_historical_financial_results | 38 → 4 | 115 秒 |
| test_historical_sec_session | 一次剖析里 206 次 | 见接线收据重建 |

`test_historical_coverage` 没有打开块：它有一例按解析调用次数断言“零调用”的仪器，打开块会让那条断言失去意义。

## 3. 对 CI 分片的影响

只改动受影响模块的权重（`tools/run_fast_tests_v2.py` 的 `SOURCE_CI_SECONDS`，取本机秒数乘 1.15；新数高于原 CI 均值的保留原值）。整层权重从 12,443 秒降到 10,903 秒，三片各约 3,654 秒，每片两条并行线，约 30.5 分钟一条线，另加检出时间。慢一些的运行器仍可能撞上 35 分钟上限，所以这仍是“够用但不宽裕”。下一次 CI 的逐用例进度行会给出实测，权重再按实测替换。

## 注错

`injections.py` → `injections.json`：页码读法 9 个、解析块 8 个。在隔离克隆里跑，每次注错用新的字节码目录。

## 不主张

- 逐块等价只在帧的 50 个期间、每份申报的全部块上测过；随机串覆盖边界字母表，但不覆盖全部 Unicode。
- 解析块的透明性依赖“解析器只读字节、返回不可变对象”这一事实。冻结解析器若将来开始读别的东西，这个块就不再透明；块的模块说明写明了这一点。

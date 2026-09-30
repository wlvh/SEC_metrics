# C03：第一版 ECD 分类标准的代理（`ecd/2022q4`），以及后来代理改了数（2026-09-30）

## 问题

全帧批次里 Enphase、Ford、Marriott、Paramount 的 FY2022 与 Pfizer 的 FY2022、FY2023 的 C03 都按名扣留 `C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND`。它们读的是报告该年度的第一份代理（2023 年的代理；Pfizer 2024 年的代理也是），这些代理的薪酬与业绩表用的是 SEC 高管薪酬（ECD）分类标准的第一个版本，命名空间是 `ecd/2022q4`，同一份文件的 DEI 也是 `dei/2022q4`。冻结的 C03 解析器只认 `ecd/` 或 `dei/` 后面跟四位数字：先在文件类型上拒绝（`C03_DEF14A_SOURCE_REQUIRED`，DEI 版本），只放宽 DEI 后又在薪酬事实上拒绝（`C03_ECD_TAXONOMY_REQUIRED`）。资料在，是程序不认这个版本名。

## 改动（`historical_dei.py`，规则文件）

DEI 版本放宽（`release_aware` 视图）已经在做同一件事：只把冻结函数问"这是不是 SEC 的某个分类标准"时用的模式换成接受三种版本写法（无后缀、季度、年后接月日）的模式。这次把冻结代码里问 ECD 的两种写法也交给同一个视图，接受同样三种写法，别的一律不变。`historical_amendment_note.py` 里 #47 自己的那一处 ECD 判断改用同一个函数（`is_ecd_namespace`），否则视图的完备性检查会点名它。冻结模块一个字节不改。

## 读出来的

用例 `tests/vnext/test_historical_ecd_release.py`（6 例，saved-source 层，零调用）：

| 公司 | 年度 | 第一份代理（视图） | 次年代理（冻结解析器） |
|---|---|---|---|
| Enphase | 2022 | 16,627,977 | 16,627,977 |
| Ford | 2022 | 20,996,146 | 冻结解析器拒绝：前任 CEO 2022 格为 nil（`C03_TARGET_FACT_INVALID`） |
| Marriott | 2022 | 18,686,271 | **18,715,093** |
| Paramount 前身 | 2022 | 32,046,006 | 32,046,006 |
| Pfizer | 2022 | 33,017,453 | 33,017,453（2025 年代理） |
| Pfizer | 2023 | 21,562,064 | 21,562,064（2025 年代理） |

另外三份第一版代理，定义给不出单一值，视图给冻结解析器的具名答案：Lumen 2022 与 Salesforce FY2023 是一年两位 CEO（`C03_MULTIPLE_REPORTED_AMOUNTS`），Macy's FY2022 的上下文按日历年而它的财年到 1 月底（`C03_TARGET_PERIOD_NOT_FOUND`）。

## 后来的代理改了数：两处，暂按缺陷撤回

放宽之前先问了一个问题：同一年的 CEO 总薪酬，后来的代理说的还是同一个数吗？`later_proxies.py` 把 33 份已存代理（检出与获取导出）里的每个 `PeoTotalCompAmt` 按期间与人列出来（`later-proxies.json`）：103 个"人—年"，其中 53 个被两份以上代理报告，**两处不同**：

- **Marriott 2022**：2023 年代理报 18,686,271；2024、2025、2026 年代理报 18,715,093。2024 年代理自己说明："All Other Compensation for fiscal year 2022 has also been adjusted to reflect an additional $28,822 related to flights Mr. Capuano took to the meetings of an outside board in the second half of 2022"，薪酬与业绩表脚注也写明 2022 年的汇总表总额 "have been corrected"。
- **Macy's FY2023**（2024-02-03 结束）：2024 年代理报 11,821,259（全帧批次已发布这个数，未被接受）；2025、2026 年代理报 11,563,739，脚注（5）："The amounts for PEO for 2023 reflect repayment of erroneously awarded compensation under the Company's Compensation Clawback Policy as a result of revisions to correct an error to previously issued financial statements."

历史路线读报告该年度的第一份代理，也就是"当时报告的数"，这与其余指标一致：它们都读目标年度自己的申报，不看后来年报里重述的比较数。按这个口径，这两个数是申报当时说的；按"后来报告的"口径，它们已被申报人自己改掉。选哪个是口径决定，不是程序问题。在所有者决定之前，两个坐标登记为缺陷（`known_result_defects.json`，按坐标、`ROOT_CAUSE_MEASURED_AWAITS_THE_CONVENTION_DECISION`）：值不改、不删，只是不计入已核实结果。

## 给所有者的问题

历史框架的年度值用"当时报告的"还是"后来报告的"？

- **A 当时报告的（推荐）**：与另外 38 个指标的构造一致；历史值不会因为新申报到来而变。两处已知的后改记在证据里，缺陷按决定释放。
- **B 后来报告的**：C03 改读报告该年度的最新一份已存代理。C03 单独这样做会让框架混用两种口径；若要全框架这样做，每个财务指标都要去读后来年报里的重述比较数，这是一项新工作。
- **C 不一致就扣留**：两份代理说法不同时按名扣留。要把后来的代理也作为 Run 的输入绑定，才可复现。

**这里有一个框架层面的盲点**：点时（当时报告的）口径下，框架从不检查任何指标后来是否被重述。C03 只是因为代理之间逐年重复报告、查起来便宜，才先被看见。

## 往年值的独立阅读：跨代理对照

同一个问题反过来就是一份独立阅读：一年的 CEO 总薪酬，除了路线读的那份代理，后来每份代理都会再报一次。`tools/read_c03_across_proxies.py`（不导入路线的任何治理模块）读登记人每份已存代理里该年的 `PeoTotalCompAmt`，只在三件事同时成立时接受：每份代理只报一个总额（占位横线按 `read_governance_facts` 的规则放在一边）、所有代理一致、其中至少一份是结果没有点名的申报——也就是路线没读过的文件确认了这个数。

对全帧批次的 9 个往年 C03 值（`content-acceptance/c03-across-proxies-read-batch.json`）：8 个 MATCH 并进入接受登记（Enphase FY2023/FY2024、Macy's FY2024、Marriott FY2023/FY2024、Paramount FY2023、Pfizer FY2024、Salesforce FY2025，登记 188 → 196）；Macy's FY2023 因两份代理数字不同不读（`PROXIES_REPORT_DIFFERENT_AMOUNTS`）。用例 `tests/vnext/test_c03_across_proxies_reading.py`（6 例，5 秒，saved-source 层）。

## 注错

- 放宽本身：`injections.py` → `injections.json`，5 个全部由为它写的用例抓到。第一次运行只抓到 4 个（`injections-first-version.json`）：把 Part III 修订检查改回冻结写法没有任何用例看得见——已存的 Part III 修订都不是第一版 ECD。补了一个构造用例（前身修订原件只改那一行命名空间声明，用例里写明是构造的），第二次运行由它抓到。
- 阅读工具：`reading_injections.py` → `reading-injections.json`，3 个全部被抓。

都在隔离克隆里跑。

## 不保证的

- 视图读出的值与次年代理一致，只说明两份文件说同一个数；内容验收另做。
- 53 个被多份代理报告的"人—年"之外，只有一份代理的年份无从比较。

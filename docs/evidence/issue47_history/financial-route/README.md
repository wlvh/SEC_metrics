# 六个金融指标的适用分支（Issue #47）

## 做了什么

A03/A04/A09/A11/A12/A13 按 `financial` 特征门控。此前历史路线只答门关着的那一侧（结构性不适用），门开着的那一侧——本帧唯一的银行 JPMorgan——没有任何历史路线，覆盖表把它们记成"仅结构适用"。复审指出这不是完成，而是一侧的实现缺口。

`scripts/vnext/historical_financial_results.py`（第 32 个规则文件）把普通路线 `ordinary_financial_results.resolve_current_financial_metric` 指向钉定期间。普通路线唯一的期间依赖是 `prepare_saved_annual_input`（取最新年报），其后全部是该准备的函数；本模块把准备显式交进来，**冻结的 Spec 检查、六个检查器、测量期间规则、失败分类与全部记录形状都原样导入**，不复制。只有两处有意差异：

1. 普通准备恰好三份证明；钉定准备还带修订件与前身目录块的证明（数据根要能重放选择），所以检查器读的三份**按 URL 认**而不按位置，其余随 Run 携带、不被读取。
2. 交给解析器的是 `original_input`（未按 DEI 重新标注的那份），因为那是普通路线读的形状；对本帧唯一的银行（日历年）两者相同。

修订件与接续主体按普通路线的方式回答：`update_status` 不是 `ORIGINAL_INPUT_READY` 就给普通路线自己的扣留结果。**不**查已批修订政策——普通路线的政策接线没有覆盖这一族，放宽一个指标接受哪些输入不是移植该做的决定（住宿移植查了政策，那个差异已记录）。

`historical_results` 在门开时派发到本路线（与住宿同位置、同理由：结构路线保留门关的一侧）；覆盖表 `WIRED_FINANCIAL_METRICS`，`STRUCTURAL_APPLICABILITY_METRICS` 随之为空。

## 怎么验的（`tests/vnext/test_historical_financial_results.py`，9 例）

- **替换即普通路线**：同一份普通准备交给普通解析器与本解析器，六个指标在 JPMorgan 真实最新年报上**返回的每个字段都相等**，且都是 APPLICABLE/EXACT/PUBLISHED（两个相同的拒绝也会相等，所以要求交付值）：A03 1.11、A04 0.025、A09 0.0066、A11 4,791,000,000,000、A12 40,000,000、A13 42,758,000,000。冻结检查器按"整份 bundle 的每个字节"作键共享，每个指标只解析一次；若本路线构造了不同的 bundle，就不会命中共享项、而是自己算。
- **钉定准备的形状**：Marriott FY2023 的钉定准备交给两个解析器（普通那个经替换其准备函数）逐字段相同；Paramount FY2025 带 Part III 修订件的准备（>3 份证明）普通解析器按 `NORMAL_FINANCIAL_SOURCE_SET_INCOMPLETE` 拒绝、本解析器读同样三份并携带第四份；证明顺序打乱并追加一个历史块证明时读到的仍是同三份。
- **入口本身**：没有任何金融公司有可达期间，所以把银行的特征借给 Marriott FY2023 打开门、跑一遍"钉定选择→准备→解析"。这是构造输入，断言只关于读了哪份申报、交出去的是哪份准备，从不关于值。
- **门只答一次**：门关的一侧本入口按名拒绝（`HISTORICAL_FINANCIAL_METRIC_NOT_APPLICABLE`，`IMPLEMENTATION_GAP`），派发给结构路线；银行的六个指标派发到本路线（替换解析器记录被到达）。

五次注错全部被抓：按位置取证明、取最新年报、交出重新标注的准备、门关也回答、删掉派发。

## 绑定了哪些文件（测出来的）

新进程对 JPMorgan 跑完六个指标，列出加载的模块与打开的规则文件：81 个模块只有本模块未绑定（已写进 `NEW_RULE_FILES`）；22 个非证据数据文件里只有一个未绑定——`docs/evidence/issue_28_prb_policy_revision.json`，A03 检查器经 R4 任务目录读它并按目录自带的摘要核对正文。目录已绑定所以正文实际已被钉住，但 Run 打开了它，按"清单就是 Run 打开的东西"写进 `AUTHORITY_ADDITIONS`。

## 今天没有任何位置行使它，以及一个跨路线的已测限制

- JPMorgan 每个目标期间的期间选择都以 `ORDINARY_PERIOD_SELECTION_SAVED_HISTORY_INCOHERENT` 停下（保存的目录与分片不一致），所以没有 JPMorgan 位置到达本路线。本轮移动的是"路线存在"这一层（30 个位置），不是任何交付值。
- **来源集发现只读主 submissions 文档的 recent 块**（普通路线、钉定的 accession 路线、Company Facts 与零 AI 报表路线的 `_exact_set` 都如此）。`measure_target_row_blocks.py` 实测（`target-row-blocks.json`）：JPMorgan 主文档只列 2025-08-15 到 2026-08-17 的申报，FY2024 的 10-K 行在历史块 004；Salesforce 的 FY2023、FY2022 两行也不在主文档。加上 JPMorgan 三个尚未发现的期间（其 10-K 必然早于 2025-08-15），**50 个目标期间里有 6 个**的目标行只在历史块里。这些期间的原件与目录即便全部取得，上述路线仍会在来源集发现处以 `Source-set references differ from submissions discovery` 停下——**这是实现缺口，不是披露缺失，也不是获取能解决的**。今天没有任何一个"原件已存且行在历史块"的期间，所以没有真实正例可测；修法（按目标行所在的块作为来源集的清单，冻结路由器本就接受历史块）已知，待有正例或在获取之前做。

## 端到端：唯一一个能跑通银行期间的根（`recorded_bank_run.py`）

本仓库保存的 JPMorgan 目录里，历史块正文都落在索引声明的区间之外，所以每个期间都停在期间选择。刷新链（`tests/vnext/test_historical_sec_session.py` 的 `ARefreshIsFinishedWhenThePlanStopsAskingForIt`）造了一个记录根：索引按已存的六个历史块自身正文重新推出区间，其余全部是本仓库已存的字节。在这个根上 FY2025 能选出来，而且它的选择**读了六个历史块**（上一年 10-K 在块 004 里）——这是本仓库唯一一个"原件已存、且选择读历史块"的期间，所以它是下面两个缺陷唯一的真实字节正例。它是 `RECORDED_TEST_ONLY`，证明的是机制，不是交付。

跑这条链（选择→装入新数据根→issue_47_v1 下原生 Run→冻结→公共行→另一进程冷读）**先后撞上两个从未被任何可达期间碰到的缺陷**：

1. **安装器从来源根读 Requirement**（普通路线的安装器从运行树读）。任何外部来源根——获取会话产出的正是这种根——都在复制任何东西之前停在 `Requirement JSON is missing or unsafe`。从没有调用方传过来源根，所以没人见过。修在 `historical_run.install_historical_run_inputs`：读运行树的 Requirement。
2. **钉定输入不带选择读过的本注册人历史块**。修 1 之后，安装在新数据根里重建时重推自己的期间选择，停在 `Request-ledger locator evidence is invalid`——前身年份当初补带前身目录块之前撞的就是这一个（`recorded-bank-run/before-own-blocks.log`）。修在 `historical_annual_input.prepare_original_historical_input`：选择记录的 `loaded_inventories` 除主文档外每一块的证明都随输入携带。**对所有可达期间零变化**：12 个可达期间的选择都只读主文档，实测证明数不变（用例断言 Marriott FY2023 仍是 3 份）。受影响的是实测会读块的期间：Pfizer FY2021、Salesforce FY2022–FY2024（上一年或本年那一行在块里），以及 JPMorgan。

修后三个指标跑通，逐项与普通路线在同一份申报上的值相同：A04 0.025（年度）、A03 1.11（季度平均窗口 2025-10-01..2025-12-31，Run 坐标走结果窗口）、A09 0.0066（瞬时）；三份结果在 `recorded-bank-run/`。A04：Run `FROZEN`、公共行 `MDA_OK`、1 条证据、另一进程冷读同 run_id 同 result_id、零新增调用。

仍未解决、也没有真实正例：**目标行本身在历史块里**（JPMorgan FY2021–FY2024、Salesforce FY2022–FY2023）时，四条钉定路线的来源集发现仍只看主文档的 recent 块。修 2 只保证这些块随输入携带；发现本身还要改用目标行所在的块作清单。

## 不主张

任何 JPMorgan 往年的值；来源集跨块发现已实现；普通路线本身的内容正确性（本轮只证明移植与普通路线等价）。

## 同一根上的整期扫描（`recorded_bank_sweep.py` → `recorded-bank-sweep.json`）

同一个记录根、同一个期间（JPMorgan FY2025，选择读六个历史块），把每个有历史路线的指标都走一遍装入→原生 Run→冻结→公共行，每个路线族抽一个 Run 在另一进程冷读。`RECORDED_TEST_ONLY`，零调用，closure `sha256:cb95b4ad…`（运行树为 2f130249 内容加注册补丁）。

38 个位置：**37 个出公共行**——17 个带值（A01–A13 十三个与普通路线同一申报上的值一致，另有 C02、C03 40,632,724、D01、D02），12 个结构性不适用（B 族对银行不适用、B13 不在已批范围），8 个带具名原因扣留；**D04 按名停**（`HISTORICAL_SEMANTIC_ASSESSMENT_NOT_REGISTERED:LIVE`，没有登记评估，不发调用）。D03 没有历史路线，未尝试。

**7 个扣留由同一次失败请求挡住**：C01、C04、E01–E05 的原因全是 `LATEST_SOURCE_REQUEST_FAILED: …/0000019617-25-000332.hdr.sgml`——账本里这份 8-K 头文件最近一次 GET 没有响应（status 0，2026-07-09T08:55:56Z），此前三次都是 200。`saved_source` 按设计拒绝"最近一次失败"的网址，所以旧的成功不能顶替；与 Salesforce 那六个事件加 C04 同形。**这是第一个阻断，不等于唯一阻断**，所以逐份量了事件遍历自己要读的材料（`measure_bank_event_material.py` → `bank-event-material.json`）：窗口里 20 份 8-K、跨 7 个块，正文 20 份全存，头文件 19 份可用，**不可用的恰好就是这一份**。遍历之后的步骤要这一份可用才走得到，没有量；C04 另读上一期审计师申报，也没有量。B06 是普通路线对银行自己的具名限制（`BANK_FINANCE_LEASE_COMPLETENESS_NOT_ESTABLISHED`），不是缺来源。

**首跑 B13 失败，是安装器的缺陷**：`[Errno 2] No such file … 02_指标定义_SEC_10公司单年指标.md`。B13 的范围从已批定义读，定义在仓库根，路线从数据根读它，而安装器只复制 `config/` 与 `catalog/`。安装器改为装入所有非代码的执行授权输入（`scripts/vnext/historical_sec_session.py`，两个方向各有用例、两个注错都被抓）后，向同一个根补装，B13 重跑得出公共行（结构性不适用）。

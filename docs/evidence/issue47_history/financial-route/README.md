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

## 不主张

任何 JPMorgan 往年的值；来源集跨块发现已实现；普通路线本身的内容正确性（本轮只证明移植与普通路线等价）。

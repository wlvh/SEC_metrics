# D04 的单对象上限：只在冻结分组拒绝时放宽（2026-09-30）

## 问题

全帧批次里 Pfizer FY2022 的 D04 在来源准备处以 `SEMANTIC_SINGLE_SOURCE_OBJECT_EXCEEDS_INPUT_BOUND` 失败。冻结的 D04 来源分组（`r6_semantic_source._group`，#28 的代码）要求任何单个来源对象编码后不超过 `max_single_object_payload_bytes` = 300,000 字节。

## 先量

- `probe.py` → `probe.json`：在改动之前，把冻结分组原样跑在导出恢复的根上，只观察每一行单独编码的大小。超限的恰好一个对象：一个 inline XBRL `continuation`（续接对象，把一个文本块事实的正文接到文档的另一处），内容是养老金计划资产表（"D. Plan Assets"），原始 XML 296,067 字符、可见文字只有 5,434 字符，编码后 313,218 字节。其余可见文字块最大 3,705 字节、原生事实最大 8,395 字节。
- `scan.py` → `scan.json`：对已存的 940 份带 inline XBRL 的文档用同一冻结解析与压缩逐份量最大的补充对象。超过 300 KB 的帧内年报有 5 份：JPMorgan FY2021/FY2022、Pfizer FY2020/FY2021/FY2022（外加帧外的 Bank of America FY2025），全都是 `continuation`。**单对象的参考 token 数是 132,000–154,000**，在请求自己的上限之内：请求上限是参考 token 加 4,096 输出预留不超过 200,000，并且单个请求体不超过 8 MiB。今天批次只碰到 Pfizer FY2022，因为另外四份所在的期间还停在期间选择上，要等延伸批准之后刷新历史分片。

所以 300 KB 这个字节数是"放得进一个请求"的代用判据，而这几份文档正好是代用判据与真实判据不一致的地方。这是开发缺口（资料在、程序不处理），不是披露不足。

## 改动（`historical_semantic_source.py`，规则文件）

- 只在冻结分组对一份文档**恰好**以单对象上限拒绝时，才用后继上限重分这份文档。其他拒绝原样抛出；冻结分组能接受的文档一个字节都不变。
- 后继策略与冻结策略只差一个数：`max_single_object_payload_bytes` 取请求自己的字节上限（`continuous_request_context.MAX_BYTES`，8 MiB）。分组目标 `max_unit_payload_bytes`（150,000）不变。是否放得进请求，仍由请求构造时冻结的 `measured_groups` 按参考 token 判定，放不进就以 `CONTINUOUS_CONTEXT_SINGLE_SOURCE_UNIT_EXCEEDS_BOUND:<unit_id>` 点名拒绝。
- 用 `release_aware_with` 实现：冻结的 `_group` 只换它读的 `POLICY`，冻结的 `_native_units` 只换它调用的 `_group`。
- 文档条目带 `single_object_bound`，记下冻结上限、后继上限与依据，并点名每个超过冻结上限的单元。不拆分、不截断、不省略任何对象。

## 实测

- `requests.py` → `requests.json`：Pfizer FY2022 的 D04 由失败变为 28 个请求，全部在上限之内，合计 4,307,695 个参考输入 token。记录只点名那一个 313,218 字节的续接单元。**这是一笔大的调用量**：已批的 35 个请求里没有它，按条申请时要把它单独列出来。Marriott FY2023 作为对照，4 个请求，没有 `single_object_bound`。
- 已批的三个 D04 位置（Marriott FY2023/FY2024、Paramount 前身 FY2024）改动前后重量（`approved-positions-remeasured.json` 与 `approved-position-remeasured-without-the-change.json`）：**摘要逐个相同，所以这个改动不移动它们**。原有的差分用例（钉期来源等于冻结构建器输出，含 `semantic_source_id`）照样通过。
- **顺带查出一件与本改动无关的事**：这三个位置今天的请求摘要与 09-28 提交的计量（`../model-egress/d04-request-measurement.json`）不同。请求体字节数逐个相同，参考 token 数相差不超过 18，所以变的只是请求里的哈希；原因不在本改动（上一条已测），而在期间选择的身份：`dump_d04.py` 在提交 `9f3f4d95`（计量当时）与当前各把 Marriott FY2023 的来源与请求（去掉单元正文）完整导出，逐字段比对只有 19 处不同，全是期间选择的 `selection_id`、`source_set_identity` 与由它们推出的来源、请求编号。历史目录的身份包含目录模块自己的哈希（`normal_history_catalog.catalog_identity` 的 `catalog_module_sha256`），而 09-30 的提交 `509ac1ce`（历史分片一致性）改了这个模块。所以请求摘要不只跟请求内容走，也跟目录模块等身份文件的字节走。结论是：**模型批准正文在所有者发布之前必须从新计量重新生成**。提案工具会重算摘要，与计量不符就拒绝写出，所以旧正文不会被悄悄沿用。
- 用例：`tests/vnext/test_historical_semantic_bound.py`（8 例，约 27 秒，saved-source 层）。Pfizer FY2022 从导出读：冻结分组拒绝它；后继记录并点名唯一的超限单元，该单元就是从申报逐字符复制的那一个续接对象；超过分组目标的单元都只含一行，与冻结规则相同；该单元单独放进请求是合规的，两倍大小的单元被请求构造按名拒绝。Enphase FY2025 从检出读：结果与冻结分组完全相同、没有记录。另有两例：别的冻结拒绝原样抛出、后继不被调用；后继策略只差一个数、两个视图的替换关系用 `overrides_of` 读出。
- 注错：`injections.py` → `injections.json`（6 个，在隔离克隆里跑）：对照通过，6 个全部由为它写的用例抓到；其中"两个视图只换了 `_group`、没换 `_native_units`"同时让类夹具失败（Pfizer 那一类建不起来），但具名用例 `test_the_successor_policy_changes_one_number` 也抓到了它。**第一次运行漏了一个，原因在注错本身**："不写记录"那一个把返回值写成 `{} or {...}`，空字典为假，表达式照样返回记录，注错什么都没改（`injections-first-version.json`）；改成 `{} if True else {...}` 后被 4 个用例抓到。够不到目标代码的注错不是"没人抓得住"的证据。

## 不保证的

- 这让 Pfizer FY2022 的 D04 能建出请求，不让它有结果：D04 的往年位置都要等 #47 自己的模型调用许可，而这 28 个请求不在已批的 35 个里。
- JPMorgan FY2021/FY2022 与 Pfizer FY2021 要等分片刷新后才走到这里。它们的单对象 token 数已量过（最多 153,749），整份请求尚未构造。
- 零 SEC、零模型调用。

# D01：跨两部分的运行页眉不是标题（JPMorgan “Parts I and II”）

## 问题

已登记的四条缺陷 `D01_JPMORGAN_{2021,2023,2024,2025}_RUNNING_HEADER_PARTS_I_AND_II_TAKEN_AS_A_HEADING`：JPMorgan 年报每页顶端印一行运行页眉，Item 1A 的各页是 “Part I”，Part I 结束的那一页是 “Parts I and II”。四份年报里那一页正好收尾 Item 1A（页上有最后一个风险因素的结尾和关闭 Item 1A 的 “Item 1B.” 标题），所以这行页眉落在 Item 1A 范围内，整块加粗、独立成块。冻结选择器（`risk_signals.risk_factor_headings`）只跳过单个部分的标签（`^part\s+[ivx]+$`），于是把它当成了最后一个风险因素标题。

## 修法

历史 D01 链（`scripts/vnext/historical_risk_results.py`，规则文件）改用冻结函数的后继，冻结模块不改：

- `risk_factor_headings`：冻结选择器自己的源码，只做一处替换——跳过部分标签的那一支多认 `parts\s+[ivx]+\s+and\s+[ivx]+$`（`SEVERAL_PARTS`）。
- `_derive_candidate`：冻结推导 `text_results._derive_deterministic_candidate` 自己的源码，只做一处替换——函数体里导入选择器的那一行改为导入本模块的后继（`SELECTOR_IMPORT`）。

两者都由 `historical_financial_wording.successor` 编译：替换必须在函数源码里恰好出现一次，磁盘源码必须编译成已加载的代码，否则拒绝。候选的记录形状、条数与字数上限、证据检查都是冻结路线的。`create_deterministic_text_candidate` 与 `build_text_evidence` 两处都改用后继推导。#28 的普通路线不改：冻结模块被它的世代按字节绑定，是否接收由 #28 决定。

只认语料里出现的写法：50 份申报的 Item 1A 里，带强调的部分标签只有 “Part I”（冻结已跳过）和 “Parts I and II” 两种。逗号列举、`&`、三个部分都没有例子，所以不认；以后出现时会被当成标题，阅读会看见它。

## 量测（零调用）

`measure.py` → `measured.json`：50 期间批次（闭包 `500ddf5f`）的 50 个 D01 Run，用 Run 自己记录的来源引用和原件记录，从已存字节（检出或已提交的取数导出）重建文档，两个选择器跑同一份文档。

- 48 份可建；2 份（Southwest FY2022、FY2023）在选择之前按名拒绝 `D01_MULTISPAN_HEADING_UNSUPPORTED`（跨页标题，见 `../page-boundary/`）。
- 48 份上冻结推导都等于批次记录的候选。
- 后继只移动 JPMorgan FY2021、FY2023、FY2024、FY2025 四份，每份正好少 “Parts I and II” 一行，其余各行与顺序不变；其余 44 份候选逐字节相同。
- JPMorgan FY2022 的最后一个风险因素页不是 Part I 结束的那页，Item 1A 里只有 “Part I”，不移动。

## 用例与注错

`tests/vnext/test_historical_running_header.py`（saved-source 层，6 例，67 秒）：

- 构造文档：两部分标签与单部分标签一样被跳过；以部分标签开头的真标题仍是标题；两个后继只带列出的替换。
- JPMorgan FY2021、FY2025：同一文档两个选择器只差这一行；FY2022 不差。
- D01 接口给出后继的候选，证据回放通过（两处调用点都走后继）。

来源记录 `source-records.json` 由 `collect_records.py` 从批次 Run 复制，用例不依赖批次目录。

`injections.py` → `injections.json`：6 个注错（不加两部分写法、写法不锚定到整段文字、任何以 Parts 开头都算标签、推导仍用冻结选择器、候选仍由冻结推导生成、证据回放仍用冻结推导）。

## 未做

这是规则文件改动，提交会移动本世代快照，而模型出口离线验证的收据绑定快照。所以原先作为待提交补丁保存在 `../../pending-rule-changes/`，打算等收据提交之后再提交。10-03 虚拟机重启打断了正在进行的重封（98 个注错只跑完 10 个），重封要从头再跑，于是改为先把补丁作为正式提交落地、再在落地后的 HEAD 上重封（见 `../../pending-rule-changes/README.md`）。还没做的：在新闭包下定向重跑 JPMorgan 五年的 D01、按逐行阅读核对，再对重跑结果释放四条缺陷。在那之前四个坐标照旧撤回。

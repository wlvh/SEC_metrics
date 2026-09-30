# 没有 inline XBRL 的代理：C02 从封面认身份（C03 的读法见 proxy-compensation-table）（2026-09-30）

## 问题

全帧批次里 Ford、Marriott FY2021 的 C02 与 C03 以 `XBRL source contains no contexts` 失败——一个未命名的解析器错误。成因是**代理材料（DEF 14A）在薪酬与业绩（pay-versus-performance）规则之前不带 inline XBRL**：已存的 2022 年申报的代理（报告 FY2021；1 月财年末的 Salesforce、Macy's 报告 FY2022 与 FY2021）8 份全部没有 inline XBRL，2023 年起的全部都有（`scan.py` → `scan.json`：已存文档里正文开头提到 Schedule 14A 的共 43 份，含几份 8-K；没有 inline XBRL 的恰好是这 8 份 2022 年代理）。冻结的治理读取器按 DEI 事实认代理（EntityCentralIndexKey 等于 CIK、DocumentType 等于表单、名称取 EntityRegistrantName），没有 DEI 事实就在解析处抛错。

## C02：封面身份（`scripts/vnext/historical_proxy_identity.py`，规则文件）

冻结的 `_bound_source` 先跑、能答就用它的答案。它在解析之前核对记录、字节、URL（URL 由 CIK 与该 CIK 的 submissions 列出的 accession 构成），所以只有"它的解析恰好抛 no-contexts、且文档里没有任何 inline 标记"才轮到封面：

- 封面必须勾选 "Definitive Proxy Statement" 且其余四个框都不勾；勾选符号限于这些申报实际用的（☒ ☑ 与 Wingdings 的 `x` 为勾，☐ 与 Wingdings 的 `¨` 为不勾），别的符号按名拒绝、不猜。
- "(Name of Registrant as Specified In Its Charter)" 上方单独一块的名字，必须是 **SEC submissions 记录在代理申报日当天给这个 CIK 的名称**（去掉法律后缀与州标记比较）。

**为什么不用年报 DEI 名比对**：第一版就是这么做的，8 份里 3 份因为与身份无关的原因失败——SEC 的规范名与章程名写法不同（"FORD MOTOR CO"/"Ford Motor Company"、"MARRIOTT INTERNATIONAL INC /MD/"/"Marriott International, Inc."），以及年报与代理之间公司更名（年报 2 月发时叫 ViacomCBS，代理 4 月发时已是 Paramount Global）。SEC 记录带日期，这才让它成为检查：Salesforce 的代理在更名四周后申报，新名字对得上、旧名字对不上（用例 `test_the_record_s_dates_decide_which_name_counts`）。检查放在输入准入（那里读 submissions 记录，每次 Run 重放都会重做），证据的 coverage 记录身份依据。

`historical_dei.release_aware_with`：冻结函数的 release-aware 视图，并把它读的某个全局名换成后继；换一个它不读的名字、或换进一个未经视图就会问 DEI 问题的对象，都按名拒绝。

## C03：先按名扣留为实现缺口，随后接上代理薪酬表读法

已批定义写"来源：DEF 14A，优先 ecd XBRL facts；候选：CEO / PEO total compensation"。2022 年的代理没有 ECD 事实，它自己的薪酬汇总表（SCT）是已批来源。第一步（提交 `0ec71207`）只把未命名错误换成按名扣留 `C03_PROXY_WITHOUT_INLINE_XBRL_TABLE_NOT_READ`（实现缺口）；随后（提交 `825cc5f9`）接上了读法，这个理由码已不再产生，见 `../proxy-compensation-table/`：8 份里 6 份读出 CEO 总薪酬，Marriott 与 Salesforce 因一年两位 CEO 按定义扣留，每个候选都与后来年份代理的 PvP 标签逐位相等。

**这也纠正了此前一个"待所有者决定"的项**：此前记录说"是否用 2023 年起代理的 PvP 标签值作为 FY2021 值"需所有者决定。读已批定义后，首次报告 FY2021 的 2022 年代理自己的 SCT 就是已批来源，读它是实现工作，不需要改口径；后来年份代理里的标签值只作独立核对。

## 实测

- `probe.py` → `probe.json`：在导出恢复的根上走历史路线准备 C02 输入并建候选。六个可达的 FY2021 位置（Marriott 42 条、Ford 74、Paramount 84、Enphase 15、Lumen 46、Macy's 40）全部准备成功，每个输入绑定都带 `proxy_cover_identity`；Pfizer 与 Salesforce 在期间选择处停下（历史分片不一致，需刷新，在延伸批准里）。**这些摘录条数不是内容验收**：选择器是在 10 份 2023 年后的代理上写并核对的，2022 年的版式没读过。运行时检出里还有未提交的 #80 改动（只涉及 D02 路径）。
- `injections.py` → `injections.json`：第一次 14 个注错，13 个由为它写的用例抓到；"输入层不调用名称检查"那一个按设计不被单元用例看见（它的检查是上面的 probe 要求每个绑定都带封面身份），也如实未被抓到。接上 SCT 读法后，关于 C03 扣留理由的那一个注错随之失效，移到 `../proxy-compensation-table/injections.py`；本脚本余下 13 个在最终代码上重跑。
- 用例：`tests/vnext/test_historical_proxy_identity.py`（23 例，读导出里的 8 份真实代理与已存 submissions）、`tests/vnext/test_historical_dei.py` 新增 5 例。零 SEC、零模型调用。

## 没做的

- 定向原生 Run（这六个 C02 位置、这些 C03 位置）要等全帧批次跑完、运行树同步之后。
- 2022 年代理 C02 摘录的两向阅读。

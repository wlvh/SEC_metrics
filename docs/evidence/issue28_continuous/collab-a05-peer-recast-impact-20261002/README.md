# #47 历史 A05 重述问题在 #28 当期 JPMorgan 的影响

固定读取 #47 提交 `94cbc3e7e6af372d0ad8349585241fdbd2d0ed4e`，其缺陷登记 blob 为 `7f4413f2b9076ecfaa2c4c7815cd2ed138fe73b6`。新增的 JPMorgan FY2021 A05 缺陷是目标年报重报上一年资产数值，而旧结果用了上年首次报告值；同次增量另有 Southwest FY2022/FY2023 D01 多跨度证据缺陷。两者都是对方历史期间，不能仅按指标名撤回 #28 当期结果。

`measure.py`只读 #28 已归档的 JPMorgan FY2025 A05 原生 Run，先按现有 `material-index.json` 重验 `records.jsonl` 的归档对象哈希，再按 SourceReference 重验原 Company Facts 字节哈希；从保存的三个实际选中 claim 运行固定 peer `paired_measure_problem`。所选上一年资产为 **4,002,814,000,000**，目标 FY2025 年报在同一 Assets 概念下报告 FY2024 同值。peer 后继的同概念重述护栏在此精确旧结果 `sha256:f8f2a182897cd8ab4dd3f0ad16c399fc8ba259cc4c1706ff4db59e76ffd68639` 上返回无问题。

随后对 #28 **当前累计 `source-inputs` 根**用现有普通解析入口独立重建 JPMorgan A05/A06：前期申报可找到、`prior_error=null`，两项都是`PASS`；A05数值相同，当前候选Result ID却是新的`sha256:b4af4d3bb42610f98df83d72080b168a4ed4cf25baa9e9a692b6bf5b72e6b9d7`，不能把两个身份合并。对这个当期新候选重新执行peer护栏，也没有重述问题。故本次**不新增扣留**，也不把peer FY2021的结果信用转入本方；此处只核对该一项可比性风险及当前输入解析，不等于独立验收 A05 全部来源、公式、原生新Run或390。

开始时曾尝试直接从**仓库自带的旧来源根**重建 JPMorgan A05，得到既有 `NORMAL_COMPANYFACTS_PRIOR_HISTORY_SNAPSHOT_CONFLICT`，因而没有选中上年 claim。该根不能用来判断已归档有值 Run，也不能代表已刷新的 #28 累计来源根；上面的重新执行把两者分开了。脚本禁网，账本与累计来源日志哈希前后不变，没有发 SEC/模型请求、修改旧 Run、重新打包或动用 #47 运行根。

同一 peer 增量的 Southwest D01 多跨度旧证据缺陷与本方已做的跨页误合停用方向一致。本方十家当期候选在 `865d8220` 已逐一核对前后哈希未变，Paramount/Marriott 两份私有内容又完成限定原文复核；无需为历史 Southwest 两年重审当前十家。D02 共用核心和 C02 选择器在本次 peer 增量未改，原定归属和待决范围不变。

`measure_current_ten.py`另从同一个#28当前累计来源根依配置十家公司顺序重建A05：在现有适用性规则下，九家为`TRAIT_NOT_APPLICABLE`，仅JPMorgan FY2025有值；该唯一有值结果对固定peer新护栏仍无问题。`current-ten.json`逐家保留准确终态、Result身份、选中claim与前期来源状态。故没有遗漏另一家当期有值A05的同类重述缺陷，也没有因此新扣留；这仍非新规则已经接入普通运行或所有A05原文内容均独立审完。

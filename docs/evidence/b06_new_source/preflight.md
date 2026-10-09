# B06 新来源预检（执行准备）

2026-09-11 从干净同步 main 92fdd0e 建立 task/b06-new-source，原 stash/worktree 保留。
委托原文见 delegation.md；预算 provider≤2、paid≤2、SEC≤4，零自动重试。

| 项目 | Southwest | Salesforce |
|---|---|---|
| 固定 accession | 0000092380-25-000024 | 0001108524-25-000006 |
| 实际期末 | 2024-12-31 | 2025-01-31 |
| 提交日期 | 2025-02-07 | 2025-03-05 |
| 已有可信材料 | submissions、Company Facts、同申报 XML | submissions、Company Facts、同申报 XML |
| 缺少必要材料 | 完整 primary HTML，用于独立资产负债表/附注扫描与非Git新准入 | 同左 |
| 预计 SEC 请求 | 1 | 1 |
| 原始/修订 | 当前保存 recent block 无同期间10-K/A；以原始提交计算，后续修订状态单列 | 同左 |

两样本来自 PR42 当前普通10-K之前最近的完整普通10-K，不根据文件名选期。
清单原始字节不改；模拟历史选择通过显式“前一份普通申报”规则表达。
实际财年标签仍需各自原件 DEI 核验；Salesforce 不调用自然年限定 annual_input 入口。
当前 Company Facts 是跨申报快照，计算仅取目标 accession/期末/主体。

实际调用链：受信导入/受限 SecHttpClient 获取 → 封存申报选择 → 新来源 create Run
→ 原生 validate_and_freeze_run → 原生 load_frozen_run → 新分支来源/关系/计算重验。
完整候选封包不在本轮路径中。新分支必须由 Spec resolver 明示选择，证据缺失不能退回旧分支。

受信获取记录在安装代码拥有的 .git/b06-source-authority 中；普通输入只引用记录，
不能通过自造匹配正文/headers/ledger 获得登记。真实获取前持久预留请求名额，
缺 terminal 保持 UNKNOWN。导入以固定受审main原获取ledger及immutable body/header为依据。
交付后另导出并固定 checkpoint 摘要供离线携带；首次准入不能依赖此后置归档。
信任边界不覆盖同时控制受信代码、执行身份与历史记录的操作者。

检查范围在选择公式前建立：完整资产负债表、完整借款及租赁附注、关联政策与融资披露。
计算概念白名单不裁剪该集合。有限关系条件实现与反例完成后再执行两份原生验收。
先在PR42已审材料上开发；确定性方式足够时provider/paid为零，不要求消耗模型名额。

本轮真实 S1/S2 独立核对方法（尚未执行真实响应核对）

审阅者：`INDEPENDENT_MODEL_SUBTASK`，`/root/runtime_boundary_review`。本文件是准备好的核对方法，不是执行成功、独立人工审阅、GitHub 批准或生产许可。新 CLI 修复未完成受审身份绑定、真实阶段尚未登记时，不生成 live PASS。

每轮输入只接受真实阶段目录及其机器生成的 ordinal/plan。核对输出只写本目录下新的独立审阅文件。运行时使用本目录 `readonly.sb`，禁止网络与本目录外写入，不调用 execute/fetch/provider 工厂，不修改来源、Run、响应或成功引用。只有原生 Run、终态和包已落盘后才核对；失败保留事实，不请求补抽。

1. 从 `stage-binding.json` 读取实际阶段与原 owner-comment 证明；从 `budget/provider-N.json` 取得 exact plan ID，再读取机械派生的 `stage/candidates/<plan ID>/plan.json`。检查 stage/slot/plan 自身内容身份、受审 head/runtime/test tree、新 Requirement closure、原预算 registration、期间及 exact predecessor 一致。用户委托批准、独立代码审阅和真实请求是不同证据。

2. 核对该候选保存的 B01/B10 manifest、records、review decisions、source/attempt 文件，记录原字节 SHA/size。输入目录由 plan 派生，不根据正确 accession 或表格位置另选来源。数据根只读调用 `annual_runtime.verify_data_root`；来源仍核对原 request ledger、manifest、immutable body/header 和原始 SEC URL。若复用旧保存 SEC 材料，明确 SEC 本轮为 0，不能把旧请求当新获取。

3. B01 独立计算：沿 Result→ExecutionTrace→输入 observation→source_reference/raw_blob 找到自身 CompanyFacts。直接读取原 JSON 的 CIK、namespace/concept 和 USD 单位列表；按实际 Run 的 start/end、accession、10-K/FY 及 observation 的 filed/frame/fact identity 核对原始事实。记录 fact 的 fy/fp，不把文件下载日期当财年。当前 B01 使用 `us-gaap:Revenues`、公式 `revenue`：独立比较原 fact value、observation value、trace resolved revenue/formula result 与最终 Result，均为同一 USD 数值。重复事实只能在所需上下文数值一致时合并看待。B03 附带结果仅列出，不当作本轮采纳或修复责任。

4. B10 原文核对：读取其完整原始 HTML，重建完整 `build_table_grid`，要求与保存的 DERIVED_ASSET 相同。核对原文 DEI/context 的主体与完整财年。按新响应自己的完整 locator 解析所指的数值格和 scope 格，记录 raw_text 与 text、原始行列/span、年度和 Occupancy 表头及相邻 `%`。值所属行必须是 Worldwide；经营范围/样本范围来自该行最近合法分组 `Comparable Systemwide Properties`。脚注 `(2)` 必须原样保留，不能接受 `(3)`、其他地区或 Company-Operated 分组。数字百分比除以 100 后应等于 B10 ratio Result。

5. 使用本轮真正的 `validate_reader_output` 和 `check_annual_evidence(requirement=<本轮新Requirement>, target_period=<真实Run>)` 对**原响应**重验。不得补 leading LF、trim、修 locator、换 source 或修改响应。检查 Evidence PASS/system_approval_eligible、同一 candidate 的 SYSTEM APPROVE、normalized scope 为 comparable/systemwide/worldwide、Observation/Trace/Result 的期间/单位/来源和 ID 完整相连。B10 成功才允许描述为新成功候选；失败时保留错误及旧成功。

6. 原生执行与 usage：只读复用 `annual_adoption.verify_saved_execution`（成功时）及 WB-3 的 `_load_execution_receipt`、marker/attempt/response 读取函数。核对 plan/request/源 grid、derived execution ID、owner/time、唯一 egress marker、独立 attempt 副本、HTTP 终态、raw response、assistant output、接受记录和 usage 均指向同一执行。每个正常年度最多一份新 execution，零 retry；input usage≤200000，缓存 hit+miss 与 input、input+output 与 total 一致。失败/UNKNOWN 或数量不确定时不生成成功结论，不追加请求。

7. 区分新响应与历史回放：记录真实 HTTP request ID、raw-envelope ID（若有）、response SHA、开始/结束时间、execution/marker 身份及父任务真实命令记录。与原材料审计列出的 FY2023/24/25 历史响应、PR38 原失败和当前正式 PR40 响应对照。不得出现 `SIMULATED_HTTP_REPLAY`/测试批准身份；如果原始 envelope 与历史完全相同或 request identity 冲突，则标为需调查，不自行补抽。assistant_output 的答案或内容 ID 与旧记录相同本身不是复用，因为合法新响应可以给出相同业务值。

8. 逐阶段聚合：每一 slot 必须有唯一原生终态，所有 stage/candidates/egress/receipt 都属于该 registration。S1 后预期累计 provider/paid=1/1，S2 后=2/2；真实数值以原生记录及父任务真实命令证据交叉核对。此前离线套件内 native test counters=2/2 只代表注入 HTTP 回放，不加入真实调用账。剩余条件修复名额不会自动形成权限。

9. 包关联：定位 context.origin.plan.plan_id 与该候选一致的完整发布包，独立检查 manifest 自身 identity、全部文件集合/size/SHA、code/Requirement、candidate snapshot 原字节和来源副本；再读真实 native_result(B01/B10)。应是 240 个坐标、327 行、两项采纳+238项继承；S1.previous=S0，S2.previous=S1，其他行期间不重贴。必要原生包重验使用现有校验器，但不重复整套昂贵集成。

10. 当前状态对照：同时记录发现的申报、旧成功候选、新候选、隔离当前发布及真实生产 current active。成功后 `current_published` 必须是实际新包，`published_before` 保留前驱。same-input 重入应无新 slot/marker/请求；失败应无新 B10 Result、旧成功引用及旧完整包不变。实际生产仍是原正式包，本轮隔离 S0/S1/S2 不写成正式上线。

11. 每次核对结束重新读取所用原文件 SHA/size，确认审阅未改字节。报告写明：本人直接检查/执行、继承的原文核对、父任务真实命令记录、尚未完成部分。若资料尚未齐全，输出 NOT_READY/不足项；不把准备材料或等待状态写成 PASS。

已有可复用只读依据：`historical-material-audit.json`（三年原材料与真实 S0）；`independent-content-regression.py/.json`（直接 V9 Reader/Evidence、完整原 HTML 重建与 26 项反例）；`final-review-material-checks.py/.json`（完整包原字节与结果/来源链接）；当前最终代码审阅记录。上述历史/离线脚本的输出不可改名充当本轮真实响应审计，执行身份和来源必须重新绑定。

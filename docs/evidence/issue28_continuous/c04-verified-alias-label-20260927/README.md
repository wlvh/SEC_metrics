# C04：原请求文档别名与已批准财年规则的显式后继接线

本轮在 #28 既有显式四形式 C04 后继中，解决两项此前相互遮蔽的阻塞：旧 Salesforce FY2025 原请求把实际 SEC URL `crm-20250131.htm` 的保存文件标作 `0002.body`，冻结 v2 的名称等值检查拒绝；当前 FY2026 年报的 DEI/Company Facts `fy=2025` 与发行人明确的 FY2026 定义冲突。后者无需新业务口径批准：既有 `config/normal_fiscal_year_labels_v1.json` 与 `normal_annual_input_v2.py` 已规定在来源定义唯一且可证明时采用发行人标签、保留元数据冲突。此前把此事列为待新批准决定是核查不完整，本轮按现有政策纠正。

代码只改变显式 `c04_registration_successor.py`，增加 `c04_verified_document_alias.py`。当冻结 v2 对确切 URL/文档名不一致抛出 `C04_SAME_CIK_FILING_REQUIRED` 时，后继先重新认证原请求日志中的完整来源证明，再按同 CIK、同 accession、真实 SEC URL 与原响应 SHA 解析同一原件；原 `SourceReference`、`request_attempt_id`、`document_name=0002.body` 和历史失败均不改签。年度事实的主体、期间、维度、重复与冲突检查保留。原 C04 v2 默认入口和冻结 `governance_signals.py` 字节不变。

财年选择调用现有 `normal_annual_input_v2`，要求其 `original_input` 与 C04 已准备的原输入逐字段相同、起止日期不变。仅当所选标签或元数据冲突实际有差异时，显式后继将标签来源、原 DEI/Company Facts 值、政策 SHA 和完整核查身份写入本次 Run 绑定；不把元数据原值覆盖成2026。`rebind-final.log`把当前未冻结 V13/V14 执行身份及三个接线收据贯通，旧 V12 与旧安装包不改。前两次重绑定脚本分别因尝试修改冻结共享模块、又误把新执行文件列入 V13 业务规则集合而被加载器拒绝；两份失败日志保留，错误编辑均撤回，最终只将新文件作为显式执行依赖登记。

已执行的证据：

- `targeted-tests.log`：26项定向测试通过，包括旧 v2 对别名仍拒绝、后继原引用和匹配证明可解析、错误证明哈希与错误 CIK 仍拒绝。
- `verify_real_saved.log`：实际保存来源中 Marriott 的旧 Result/selection/input-binding 三个 ID 不变；Macy’s 财年2025不变；Paramount无同CIK比较事实仍`WITHHELD/null`；Salesforce 以 FY2026 和原 `0002.body` 引用得到`PUBLISHED/0`来源候选。
- `create_salesforce_native.log`：不发网络请求，形成 Salesforce FY2026 私有原生 `CANDIDATE_READY` Run/公开行，Result `sha256:96553cca7232ec4860d878158cc1a01dc9bdac82b14effc0fef8c707aae688b1`。
- `cold_read_salesforce.log`：另一进程禁止网络、HTTP 与子进程，重新验收原生 Run、标签绑定、原别名身份及公开行字节，`PASS`。
- `repeat_salesforce_native.log`：同一真实来源再次触发返回`NO_SOURCE_CONTENT_CHANGE`，原成功尝试与 Result ID 被复用，没有第二个成功 Result 或调用。
- `old_southwest_cold_read.log`保存一次有意的错误代码根读取：新 V13 根拒绝旧包的历史需求快照；`historical_southwest_installed_cold_read.log`再用旧包自己安装的代码根禁网、禁子进程重读原 Southwest Run/公开行，原 Result ID 保持不变。这两种结果不能混称“新代码直接兼容读取旧字节”。
- `verify_390_coordinate.log`：现有390索引的 Salesforce/C04 本来就是FY2026数值0；本轮形成的是同一坐标的新私有版本，**新增完整坐标数0**，旧 Result 保留。
- `verify_current.log`：冻结 `governance_signals.py` 与父提交逐字节相同，V13/V14闭包、执行文件及provider/SEC/普通刷新接线收据在当前代码根有效。

边界：来源和程序链通过不等于当前十家公司C04、完整390或跨财年自动发现/更新已验收。此新补丁仍待精确SHA限定独审；真实来源无新获取、模型无调用，账本仍143/143/52。无Ready、正式采纳、部署、active切换或#47验收信用。

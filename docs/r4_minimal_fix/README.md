# R4 标签表示与失败收尾最小修复

状态：离线代码候选，标签接受边界待 owner 明确批准；未激活、未授权新调用。

## 实际差异

1. `finalize_r4_scoped_run()` 删除 validation check 中 schema 不允许的
   `error_class`。保留现有 `check/status`，错误类别继续保存在 Attempt 和
   execution receipt。不修改通用 schema，不增加历史 Run 恢复工具。
2. 提供显式离线候选 `EXACT_SOURCE_RAW_OR_TEXT_V2_OFFLINE_CANDIDATE`。
   先按原规则验证来源、表格、行列、origin、rowspan/colspan，再允许标签精确等于
   **同一单元格现有的** `raw_text` 或 `text`。scope 后续核对仍使用来源恢复的
   `raw_text`。caption 保持原有 `caption_raw_text` 精确匹配。

不增加搜索、strip 后比较、大小写忽略、同义词或标点容错，不修补模型响应，
不改数值、单位、期间、主体/口径、跨表与歧义规则。原请求/响应字节与哈希保留。
候选 Evidence 的 checks 中含候选政策标记，故与旧规则生成不同证据身份。

候选字段说明：`scope_evidence_locators[].raw_text` 可复制同一已验证单元格
提供的 `raw_text` 或 `text`，必须精确相等；本地证据永远恢复源 `raw_text`。
这是待批准的新说明。现有 provider prompt 和 live 调用仍走旧规则，未擅自更新。

## 历史与授权边界

原计划 `sha256:215277ae679bde123e51cf3ce839445e9ef152c5a9f5d0c72f74a2b6618658bd`
及 PR31 head `d3babd0ac0300d68dd58007e38caa2d7b2c27ab4` 保持原样。
历史第一次调用：provider/paid/SEC=1/1/0，usage=14075/591/14666，
`FAILED_TERMINAL / EVIDENCE_FAILURE`。原 OPEN Run 未手改，reservation 未清理。

当前 `issue_28_v2` 五文件与既有 engine 都未修改。新代码不能通过旧 execution
source hashes；此拒绝有定向测试。默认/current live 未选择候选参数。
代码合并也不会赋予新接受政策或新计划权限，不得追认旧失败或使用余下十一项授权。

政策批准后才通过既有 successor revision 机制绑定候选代码和字段说明，记录
未激活的新 closure，经既有审核/激活流程后由 CLI 生成新 pending-live plan。
不新建通用版本框架。新 plan 仍需绑定当时 clean head/tree 和真实 owner 评论。

## 离线证据的解释

`tests/fixtures/r4_label_representation/` 保存本次原始 request/response 与
`OFFLINE_REGRESSION` provenance。它没有 live qualification 或 publication credit。

测试运行候选 Python；独立临时输入目录保留已合并基线的准确来源与旧证书绑定。
代码和输入的区别是显式的：没有 mock Reader/Evidence、finalizer 或 hash validator，
但这也不证明候选代码已经获得旧 Requirement 的 execution authority。

定向测试包括真实响应旧规则拒绝、新候选的 Reader/Evidence/Review/Observation/
Calculator、九份请求的两种表示、错误主体/数值/期间/口径/单位/来源/位置负例，
以及通过真正的 finalizer 完成 FAILED 和阻止后续 transport。嵌套复核既有
composite scope 测试时也使用同一冻结输入目录。

没有重跑性能 benchmark、full acceptance、发布演练或全仓测试。
WB-7/R5/R6/Rf 不在本修复 diff 中，最终项目目标不变。

## 后续调用形状

拟保留九个 base 加三个 stability 共十二次新调用；三个 structured positives
和四类排除样例继续零调用。retry=0，reuse=false，SEC=false，publication=false。
这只是提交审核的形状，尚无新 CLI plan ID 或调用授权。若未来十二次全部执行，
连同历史失败共十三次 provider/paid 调用，不能抹除历史一次。

实际测试结果与候选内容身份见同目录 validation.json 和 candidate_review.json。

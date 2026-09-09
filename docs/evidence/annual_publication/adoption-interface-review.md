# 普通年度候选的发布采纳接口核对

独立只读核对：`/root/runtime_boundary_review`。代码基线：`1e97cd08ad26edc1e7a720550811240af1889cb3`。本记录是接口建议，不是新实现审阅、资格认证、政策激活或正式切换许可；未修改旧 Run，provider/paid/SEC 新增均为 `0/0/0`。

**结论：已有验证、冻结、投影和发布底层可以复用；缺的是“如何采纳这份普通候选”的明确规则。当前不能把 PR38 的两个 OPEN Run 直接塞进历史 R3 qualification 路径。**

## 当前接口实际要求

| 位置 | 代码事实及影响 |
|---|---|
| `run_store.validate_and_freeze_run` | 已有完整 OPEN 图重放→机械 PASSED receipt→FROZEN manifest。它会写 validation/manifest，不应对原历史 Run直接调用。单独 `freeze_run` 也允许 NOT_RUN/FAILED 审计冻结，因此 FROZEN 本身不等于可发布。 |
| `annual_runtime.validate_run_binding → authorization_fields → _validate_stage` | B10历史重验仍要求当前 runtime_tree、原绝对 Run/data/controller 路径及阶段许可。新发布代码或搬迁包都会触发不匹配；不能忽略 dirty、修改旧 binding 或重新签发旧执行许可解决。 |
| `projector._batch_manifest_from_paths` | 标准通道要求 PASSED、FROZEN、全量目标键与同一 Requirement hashes，并收录每个 Run 的所有 MetricResult。PR38 B01为旧 RUN/foundation且附带B03；B10为 SUCCESSOR_RUN/issue_28_v6。不能静默改两者的历史身份，也不能为只选B01而删除原B03记录。 |
| `ratchet_release.prepare_r3_successor / _validate_committed_qualification_run` | 固定消费R3历史完整资格周期、FROZEN qualification Run、`qualification_authorization`及`TABLE_QUALIFICATION_EVIDENCE`。普通候选即使冻结，也不具备这些资格身份。 |
| `publication._portable_frozen_run_loader / _portable_closure_files` | 标准便携重验仅分普通FROZEN与历史qualification；正式发布还要求可重验的非空 qualification binding。随意填写override或只通过staging，不能取得正式资格。 |

## 建议的最小历史只读适配

增加模块拥有的**历史候选只读校验**，返回独立的只读验证结果，不生成 `RuntimeAuthorization`，也不被任何provider adapter接受：

1. 精确核对原stage ID、owner评论正文、计划ID、源Run身份、期间、Spec/task、请求与原响应；原controller invocation/marker/attempt/terminal、SYSTEM Review、Evidence及Calculator结果仍按原政策重放。
2. 旧代码身份从已绑定Git对象或冻结authority副本重算，旧Requirement/engine按原字节验证；当前发布开发树是另一份身份。原批准已消费不妨碍读证据，但仍禁止再次执行。
3. 从原输入快照读取完整ledger/body/header，拒绝路径别名、来源漂移、错误期间和错误scope。不要跟随当前data目录的最新清单。
4. 新增不可变采纳收据，绑定完整源Run及Review assets、代码/政策、来源、controller证据的文件集合与哈希，并显式选定B01/B10结果键。完整源记录保留；附带B03不自动进入更新集合。可搬迁包必须实际携带这些字节，绝对原路径只作出处说明。

该收据可作为本轮新 `NONE_REHEARSAL` 类型完整候选包的输入。复用现有原生结果投影和证据生成函数，再复用完整包字节验证、隔离目录的CAS/read-back/rollback；普通候选的历史验证与完整版本准备之间只增加这条可重验的采纳关系，不复制AI执行器。

## 什么时候必须原生冻结

- **走现有标准BatchManifest/portable Run通道：** 派生副本须经真实 `validate_and_freeze_run` 生成PASSED/FROZEN，并有上述历史只读适配供复制位置重验。不得手改状态、由loader伪造FROZEN，或改原Run。冻结也不会自行解决不同Requirement及B03附带结果的批次规则，仍须明确接线。
- **走明确的新NONE_REHEARSAL采纳包：** 可以保留源Run的OPEN与原validation状态，由采纳收据封存已完整重放的源字节，再验证新完整包。不能把新包的验证结果写成原Run已冻结或已获formal acceptance。此选择不取消未来正式发布对采纳类型的明确政策与资格裁决。

真正新增的政策应说明：哪些普通候选可被采纳、完整版本中仅替换哪些键、其他结果如何继承、不同历史Requirement如何分别验证，以及历史资格支持到哪里。PR38新的标签/归属检查与一次已知输入成功不能冒称重新完成旧SECOND_LAYOUT/HOLDOUT/FRESH资格；保留R3历史资格只说明原版本的证据。若未来决定允许新候选沿明确采纳规则进入formal链，必须由该新政策及其独立验证承担这一变化，不能给旧资格对象换身份。

本轮可验收边界：在隔离目录生成、重验完整候选版本，并证明旧Run、R3及正式root字节未变。真实激活和正式R3切换仍未授权。

# Marriott B03 在现有 390 证据视图中的限定独审

**结论：PASS_WITH_BOUNDS。** 在指定增量范围内未发现需阻断接收的问题。这里的通过只覆盖 `--include-marriott-b03-reviewed` 对既存 Result 的较晚 Run 选择、保存来源修后证明与机械收据绑定，不是新的业务结果或正式发布验收。

审阅目标：`569ea0ad772368ce50d4b30053375a4e4ad53be6`；基线：`c7a96eae8dbd6df9f01bc4db9a14014b69f487ef`。工作区：`/Users/lyuhongwang/Developer/SEC_metrics`。起始 UTC：`2026-10-04T12:06:16Z`；结束 UTC：`2026-10-04T12:11:24.766689+00:00`。实际工具量为 9 条 functions.exec wrapper ＋ 22 次嵌套工具调用，共保守累计 **31**；普通消息共 **3**（开头、进度、最终）。未触及上限。

## 已验证的对应关系

- 较晚 Run 为 `run:ordinary-integrated:bb6ec093fb8fde7682cf83ca955c282e4d3c62471301cffaddfdbd0e915250fa`；旧 `b5e9b4cc…` Run 明确保留为 prior，不能仅凭相同 Result ID 继承修后证据。Result 固定为 `sha256:3043aa63cbf7616f9866fb93b8f69200a2246a33dfec8f1d09502a34af39a72a`。我对照了保存 Run 的 manifest、records、原始 NOT_RUN validation 和独立副本 receipt，身份、记录字节、artifact hash、V13 requirement closure、FY2025 期间均相符。副本仅 `validation.json` 与原件不同。
- 原生安装范围仍是保存的 V13 data root，安装包内没有 `b03_contract_amortization_scope.py`。现有机械收据因此只覆盖该 V13 Run 副本；URI 修复信用由另行绑定的 `exercise-repair.json`、`cold-repair.json` 和 `followup-2bbd769.md` 提供。实际读取入口固定四项必需 proof，逐项验证 hash，再核 repaired module SHA、Result、cold Run、数值及 source relation。当前修后模块 hash 实际为 `acc01df28a45c56c89d0c9c280487434b25efd0ac0ee60d8f659ce25a2b8429f`，与固定 admission 相符。未将机械 PASS 写作 V14 URI 修复的重新执行。
- 有限业务范围为 145 百万美元折旧＋313 百万美元无形资产摊销，合计 458 百万美元；135 百万美元合同取得成本收入减项排除，未量化合同履约成本摊销的解释边界保留。视图明确为 `BOUND_APPROVED_DA_SCOPE_REPAIRED_ADMISSION_AND_MECHANICAL_RUN_ONLY`，`economic_all_amortization_scope_proven=false`。来源内容审阅信用沿旧限定审阅复用；本次未重开原件业务裁定或 URI 核心独审。
- 与基线提交源码实际组装结果逐对象比较：两种既存默认组合（JPM 未选择／已选择）均完全一致。启用 Marriott 后只改变其 B03 一行，其他 389 行逐对象相同。390 分母、20 项旧产品范围限制保留；JPM 显式选择组合仍有 17 个确诊扣留坐标，未选择 JPM 的既存默认为 18 个，均维持 null。旧 parent index 字节未改。

## 独立执行及反例

指定两套测试实际运行：新增 **7/7**，既存 **19/19**，均 exit 0。另以真实 loader 在内存隔离替换输入验证八项反例：旧 Run 搭配新证明、失败 receipt、改 native 值、错误安装根、proof hash 改变、期间起点改变、proof 集合增加、扩大经济摊销声明，均拒绝。真实 CLI 的默认、单 Marriott、两选项两种顺序与 API 输出完全相同；重复选项及未知选项拒绝并无输出文件。临时 CLI 文件已由 TemporaryDirectory 清理。

日志：`receiving-tests.log`、`unchanged-view-tests.log`、`independent-probes.log`、`independent-negative-probes.log`、`bound-artifact-check.log`、`review-session.log`。

## 信用与未覆盖责任

本次没有重跑旧正常更新大链、完整机械执行、URI 修复核心、模型、SEC 或账户动作；没有操作其他工作树、spawn、源码修改、commit 或 push。保存机械执行和修后更新／冷读的历史真实性按所绑定旧证据解释，不冒充本次重跑。新 provider/paid/SEC 调用 **0/0/0**。

`all390_acceptance`、`full_current_head_reexecution`、`production_authorized`、本行 `current_head_full_revalidated` 与 `formal_adoption_or_active_credit` 都保持 false。本次不授完整经济 D&A、当前开发 head 重演、其他公司指标或统一更新／发布信用。限定通过可以供本方显式证据视图接收；正常新财报更新及统一发布的剩余责任仍按原队列处理。

工作区开始已有 `execution-state.json` 未提交变动；本次未修改该文件。输出仅位于本目录的结论与日志，审阅输入在结束时再次逐 byte 对照目标 SHA。

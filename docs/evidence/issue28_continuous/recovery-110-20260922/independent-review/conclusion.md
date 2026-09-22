# 原110受限恢复：限定差异独立审阅

结论：本次限定差异内未发现需要阻断修复的缺陷。此结论覆盖原110一次恢复、调用机会消费、成功登记和历史冷读衔接；不是全PR批准、代码合并、完整B13验收或生产批准。

- 受审提交：`d179284840d93e82835ab299cecba93b71d83100`。
- 父提交：`3883f9ca70cb1c210e66eb36479acbbe3d826f72`。
- 实际工具调用：34次，包含12次 functions.exec 编排和22次叶子调用；无子代理调用。工具额度80次以内。消息仅开始说明及最终报告。
- 范围：continuous_recovery_110、continuous_call_ledger、continuous_semantic_calls、capacity_native_assessment、capacity_assessment_input、两个调用/恢复配置、issue_28_v14绑定，以及指定恢复测试。受审工作树这些文件与受审SHA一致。

## 已独立核实

1. 外部授权：实时读取 Issue #28 及评论 [5775635612](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5775635612)。评论由 wlvh 发布，created_at 与 updated_at 相等；实时 body、评论/Issue标识、URL和时间与保存件一致，正文SHA为 `daefa36b97048ab0bce8e94d1f5518af0e438e85558d7b81be9114fd0b0c3de7`。这是明确用户委托的代登记，不称为用户亲自输入或一次代码审查。
2. 唯一失败与原请求：授权绑定原根、binding、110的intent/terminal、request digest和原request/source字节。独立调用只读 validate_original 核验真实110为 HTTP_402 / FAILED_TERMINAL / [1,1,0]，没有assistant输出文件。恢复配置不增加240/240/80额度，不改变摘要算法；后续LIVE入口限定B13/D04。
3. 消费与重启：新claim追加并fsync后才写intent；恢复标记只允许首次原digest重复，原110停止在申领前仍保留。新申领无terminal按最大调用计数并阻断；追加后intent写入失败通过claims/目录不一致拒绝继续。目录flock保护竞争过程，测试中两个进程仅一个领取成功。
4. 停止条件与重复：snapshot按通道和序号记录停止，仅移除指定原110停止；新402、UNKNOWN、来源真实性失败、usage未知、上下文引用不匹配仍停止。重复恢复标记、缺少标记的重复请求、删除授权、重签错误授权字段均被限定测试拒绝。
5. 旧失败保留：独立比对 before-recovery-invariants 列明的113个实际账本文件，hash和长度均未变，包括binding、初始化锚点、claim前缀及旧终态；审阅时真实 recovery-110.json 尚不存在。测试另核对原失败槽文件字节不变。
6. 成功登记：收集器先经账本和原生成功回放验证，只有授权后继成功才将原失败从当前failed_requests转存至 recovered_http402_failures；原intent、terminal、wire及授权一起保留。没有恢复记录的旧路径保持原结构，既有成功选择与回放不新增调用。
7. 冷读：在新Python进程、禁用socket连接和DNS的条件下，独立读取当前已登记的六组录制记录，原序号2–7全部重验通过，保留一个原HTTP402失败历史，当前failed_requests为空，登记文件字节不变。此步骤没有执行新请求或重新登记。当前Requirement closure为 `sha256:4cc2d5ee63b181942e41da6411d52e6cbe4763ed841c6638ec1553bba113c4ee`，与 current-registration.json 相同。
8. 执行绑定：逐个核对当前baseline的new_rule_files和execution_authority文件hash/长度，并通过原生Requirement加载验证。当前注册对应的新执行绑定与旧offline-summary中的早期绑定分别保留，未将早期执行改写为当前执行。

## 实际验证与日志

命令：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. /tmp/sec_metrics_ci_20260922_venv/bin/python -m unittest -v tests.vnext.test_continuous_recovery_110 tests.vnext.test_continuous_call_ledger tests.vnext.test_native_request_variants
```

结果：23项测试，0.835秒，全部通过，无SKIP。见 `targeted-tests.log`。

- `authority-and-binding.log`：实时评论、原110、113个旧账本文件及执行绑定独立核验。
- `cold-read.log`：当前完整六组登记独立冷读，17.469秒；input_record_id为 `sha256:0fd41b7a3b804137da1d6498affea0f3e80aca4ae0fc7bc9a93555b710850eed`。
- `final-verification.log`：交付文件存在、受审代码无漂移、日志结果检查。

## 验证边界

本次没有真实provider/paid/SEC调用，没有读取凭据、安装真实恢复记录、修改源码、commit/push、生产写入或运行大批次。没有重跑父进程已启动的fast，没有重新审查未改B13引用实现，也没有扩展至其他Issue或PR。外部授权检查使用GitHub只读请求，不计业务provider/SEC调用。

已检查既有offline_wiring.py及其保存结果，但未重跑完整模拟传输接线；本次亲自执行的正向证据是限定23项测试及保存六组登记的完整冷读。完整真实恢复是否成功、新provider响应内容是否合格、后续真实6组是否完成、完整指标Run及最终生产结果均未发生于本次审阅，不能由本结论推导。执行方仍应完成当前绑定的接线收据登记，然后按原授权只执行原110的一次新业务请求，并保留原失败及任何新停止。

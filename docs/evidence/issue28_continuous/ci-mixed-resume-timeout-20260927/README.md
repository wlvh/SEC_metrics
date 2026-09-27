# 新增混合刷新续跑材料的单项 CI 超时

`5e2a5ca9`主CI [`36326213320`](https://github.com/wlvh/SEC_metrics/actions/runs/36326213320) 的保存来源 shard0 作业 `108639357090` 已结束为 failure。原始作业日志的机器结果在`shard0-failure.json`：40个选择器中39个返回0，唯一失败是新增的`test_failed_processing_copy_preserves_recorded_capture_for_resume`，在240.105秒达到当前240秒单项限制、返回码124，未产生业务断言失败日志。它不是整个35分钟作业时限取消，也不证明恢复逻辑语义失败。

同一主CI的shard1作业`108639357083`也已结束为failure。`shard1-failure.json`保存39个选择器中37项通过、两项单项上限失败：新增正常混合续跑在240.106秒返回124，原D03整组录制材料在240.107秒返回124，均无业务断言失败文本。前一已成功head`b686814f`的D03同选择器在相同shard1实际216.596秒通过；本轮并发负载下原23秒余量不足，不能说D03语义出现新失败或新实现变坏。该作业实际总耗时1625.324秒，35分钟整作业限时未到。主CI其余作业终态另验。

同一已提交实现的本机禁网录制两条C04材料用例合计377.591秒、2/2通过，见[原材料日志](../ordinary-processing-snapshot-20260927/config-only-material.log)。GitHub并发runner上另一条旧C04恢复材料曾本地119.135秒通过、CI两次撞240秒，后来按已计时证据只提高该单项上限。本次为两个新增C04选择器各设360秒、原D03整组录制选择器设300秒，**仅这三项**改`SOURCE_TIMEOUT_OVERRIDES`；保留真实保存来源、测试断言、其它选择器默认240秒及整作业35分钟。`tools/run_fast_tests_v2.py`的runner函数体与材料测试不变，零新增业务调用。新head CI另验，不能把这三项局部资源修正预报成主CI全绿。

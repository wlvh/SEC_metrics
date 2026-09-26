# C04 正常更新限定回修

精确审阅 `d77a604a` 的结论见相邻 `c04-normal-update-20260926/independent-review/conclusion.md`，原 `NEEDS_FIX` 不改。本次只回修两项：C04 新控制器把成功终态的 `publication` 与来源信用分别对照已重放原生 Result、已验证的保存运行绑定；正常更新 CLI 在执行前拒绝重复或不受支持的指标。旧 `ordinary_update_cycle.py`、`normal_run_v3.py` 与其默认路径仍未修改。正常更新配置绑定新控制器字节，旧控制器录制状态仍按原提交身份保留，不拿新代码冒充对旧记录的原位续跑。

`targeted-test.log` 保留首次测试失败：测试直接使用 macOS 临时目录别名路径调用内部核验，触发 `UPDATE_STATE_PATH_ALIAS`，尚未触及受测信用条件。把测试状态根规范化后，`targeted-test-retry.log` 的两项测试通过（161.677 秒）：Marriott 保存原件产生 `PUBLISHED/0` 原生 Run，相同输入不重建；重签成功终态中的 `publication` 或 `source_credit` 后，从完整 `run_once` 重读均被拒；重复传入 `--metric C04` 在创建状态之前拒绝。测试禁用网络；没有发 SEC、模型或付费请求。

先前两份真实保存来源的录制版本、故障与中断恢复、Paramount `WITHHELD/null`、B01+C04 混合入口及独立冷读保留在前一目录。这些长链的来源选择、Run 创建和版本差异代码未变；本次修复只加强成功终态摘要核验。它们不是新财报实际发现/获取、十家公司全部 C04 完成或生产批准。当前新控制器的完整刷新链接线另验，不把本次 CLI 回修写成该入口已经接通。

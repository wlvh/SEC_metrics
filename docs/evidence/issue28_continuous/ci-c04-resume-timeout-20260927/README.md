# C04 两次来源续接材料的 CI 单项限时

修复对象是 `tests.vnext.test_c04_refresh_resume.C04RefreshResumeMaterialTest` 的**单项测试资源限时**，不是 C04 业务规则。`2ab35195` 主CI [`36302409265` 的 shard1 作业](https://github.com/wlvh/SEC_metrics/actions/runs/36302409265/job/108572396884) 于240.104秒返回124，日志只给出 `SOURCE_MATERIAL_TIMEOUT_SECONDS=240`，没有业务断言失败；前一 `f5e7bc0d` 的[对应作业](https://github.com/wlvh/SEC_metrics/actions/runs/36301428746/job/108569658806) 同项在240.053秒返回124。`9fa84fc2` 的[同项作业](https://github.com/wlvh/SEC_metrics/actions/runs/36298137866/job/108560689148) 曾在163.194秒返回0。这三份远端记录说明同一完整入口有资源耗时波动，**不能证明业务语义通过或失败**。

`time_resume.py`对原测试方法做一次有界本机分段计时，不替换真实保存材料：`time_resume.log`记载119.135秒/1项通过，第一次录制来源与更新65.738秒、两条篡改拒绝0.122和4.635秒、带认证前驱的第二次续接和原生更新45.358秒、重复前驱拒绝0.044秒。录制SEC真实外送0，模型0。两个有意义的来源/Run阶段均在执行，没有可从测试中直接删除的冗余整链。该本机时间不保证CI时间。

因此只在 `tools/run_fast_tests_v2.py` 的已有单项覆盖表末尾为此 selector 设 **360秒**；其他保存材料默认240秒、D03局部300秒及整体CI作业35分钟不变。即使这项在360秒完成，原shard1约20分钟的总耗时仍有整体作业余量。该配置不跳过来源认证、篡改负例、失败保留、第二次真实材料处理或独立结果核验。`verify_selector_corrected.log`用替身进程核对实际传给原runner的timeout=360及其他上限不变；第一次脚本因缺少`tools/`导入路径而在检查前退出，见`verify_selector.log`。配置改后未重复执行119秒的已通过本机材料，须以新head CI检验托管runner结果。

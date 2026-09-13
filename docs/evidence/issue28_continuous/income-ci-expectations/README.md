# 收入非数值结论的CI预期同步

996cc11的9个CI job成功，source-material仅两个选择项失败：旧测试仍把B01/B03视为WITHHELD，并把所有非WITHHELD/非N_A终态计作“number”。新原生行为已由原Spec年度长度守卫证明NOT_MEANINGFUL，因此这些预期已经过时。

本次只修改测试计数和断言，不改运行代码或来源：20坐标明确区分15数值、1结构不适用、3WITHHELD、1NOT_MEANINGFUL；非数值必须value=null，数值必须非null。B03依赖检查保留B01/B03完整集合，并要求两者ANNUAL_DURATION_OUT_OF_RANGE和真实输入观察、实际146天坐标。没有删测试或放宽成“任意终态均可”。

实际命令：PYTHONPATH=scripts python3 -m unittest tests.vnext.test_normal_zero_ai_results tests.vnext.test_normal_run_inputs。14项全部PASS92.716s；原CI完整日志/原汇总与修后本地日志在压缩包中逐字节读回核验。新提交CI仍以实际Checks为准，不借旧head或本地结果宣称全CI通过。

原31次真实获取、来源/Run/失败/规则和独立审阅范围不改变；没有新调用、合并、采纳、部署或active切换。下一核心语义验证需要当前进程的DEEPSEEK_API_KEY；预算已批准，不是费用待批。B13、D03/D04、390、更新、发布/故障回退恢复/旧入口退出及未覆盖独立审阅仍未完成。

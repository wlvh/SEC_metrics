# Paramount D04：十组真实来源的完整原生候选

原113因来源无损表示问题保持失败和计数；本批第179次使用修复后的原文来源、同一业务摘要得到新成功，第180—188次依次完成其余九组。`calls.json`保存十组各自原账本编号、摘要及终态，均为原生`SUCCEEDED`，没有自动重试或SEC请求。新的完整评估只采信十条新成功；原113仍在历史链中。

`finish_company.py`从十组真实成功登记完整输入，生成普通原生Run与两个公开CSV；结束阶段新增调用0/0/0。`finish-summary.json`为FY2025（2025-01-01至2025-12-31）`TEXT_V1`候选，reason=`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`，质量`NONE`、适用性`APPLICABLE`。此结论仅说明规定的完整保存来源范围内没有发现持续经营疑虑披露，不是财务健康保证或正式生产发布。

`persist_cold.py`把Run及安装副本保存到`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/native-candidate-results-20260924/paramount_skydance_paramount_global`。683个文件与工作副本逐字节哈希一致；独立Python3.9进程在空工作目录从保存副本加载运行模块，禁止网络/子进程，重读Run并核对公开CSV字节，`cold-summary.json`和`cold.log`返回0。没有改变active指针，未重新打包旧材料。

至此D04十家公司均有完整真实候选；统一390、常态更新、业务审阅与正式采纳仍是独立验收。B13两家尚未取得本批完整结果。

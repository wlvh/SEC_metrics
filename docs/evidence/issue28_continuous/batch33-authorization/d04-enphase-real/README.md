# Enphase D04：六组真实来源的完整原生候选

第172次为服务端HTTP402失败，原记录保留。用户另行批准的一次同摘要恢复在第173次成功；第174—178次依次完成剩余五组，`calls.json`记录每组原账本身份与终态。新成功与原114/172失败分别保留，当前评估仅使用六条新成功。无自动重试或SEC请求。

`finish_company.py`从六条原生响应登记完整D04输入，创建同一普通Run并保存公开格式行；本地结束阶段新增调用0/0/0。`finish-summary.json`对应FY2025（2025-01-01至2025-12-31）的`TEXT_V1`候选，reason为`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`，质量`NONE`、适用性`APPLICABLE`。含义仅限完整保存来源的规定范围内没有发现持续经营疑虑披露，不是财务健康保证或正式生产发布。

`persist_cold.py`把Run及安装副本保存到`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/native-candidate-results-20260924/enphase_energy`；681个文件与原始工作副本逐字节哈希相同。独立Python3.9进程从该持久副本加载运行模块，在空工作目录中禁止网络/子进程，重读Run并逐字节比较两个公开CSV，结果见`cold-summary.json`及`cold.log`，返回码0。没有改变active指针，未打包或重做旧公司材料。

此处证明一家公司完整真实候选及可读性，不能代替全部D04、十家公司×39指标、正常更新或生产采纳验收。Paramount尚需独立的完整Run和冷读。

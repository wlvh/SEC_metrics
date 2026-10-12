# D04原回答材料与有限恢复核查

本次实际只读原#28账本 `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`，不创建调用、Native Evidence、公司Run或业务接受。执行源码来自公共B06工作树的当前D04模块（本地d31884db；该D04模块及共享语义模块与原执行现场相同），不是重放旧录制答案后改签成新模型执行。

## 实际读取结论

`inspect_saved_responses.py`遍历原195个申领，选出已有D04请求的98条；核对terminal列出的原文件哈希（包括请求/源/原响应/原执行材料），以及source packet引用的SEC原件与头文件哈希。对93条原SUCCEEDED的assistant输出调用现有 `d04_native_assessment.validate_response`，没有构造任何成功记录。原69、71、113、114、172五条FAILED_TERMINAL只归历史失败，不尝试升级。

实际11.923s，98条未发现所检查的材料缺失或哈希不符；93条当前响应检查通过，零未决。分布：Ford11、Pfizer11、Marriott4、Southwest6、JPMorgan27、Salesforce5、Lumen8、Macy's5、Enphase6、Paramount10。这里93是请求组数，不是93家公司或新增公司结果。完整结果见 `inventory.json`，原运行日志 `inspection.log`。

这些记录的分类是：`CURRENT_RESPONSE_CHECK_PASSED_REQUIRES_SELECTED_INPUT_MATCH` 或 `HISTORICAL_FAILURE_ONLY`。前者表示具有原回答且当前结构/必要语义检查未拒绝，仍须与实际选定来源、期间、当前请求及合同逐字节对应，才能沿现成重放入口消费。它不证明模型没有漏报、没有错分或完整公司当前合同已接受；也不替当前媒体覆盖或新输入需求授予信用。尤其113已发生的来源表示损失不因原件哈希存在而被修复。

读取期间claims字节和195行保持；原累计provider/paid/SEC=143/143/52，剩97/97/28不变，未知费用保持null。没有provider调用、SEC GET、账户/探针或新响应登记。

## 第173次恢复样本

从原173目录复制一个原调用的材料、六个必需来源/头文件和原账本metadata到独立目录：

`/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d04-call173-restored-20261012`

27个文件、16,196,958字节；复制0.035s，独立进程读取0.221s。独立 `restore_reader.py` 核对全部复制文件的哈希，读取原request/response和原SUCCEEDED，再调用同一当前响应检查，零未决。原claims及原call全部字节保持。

此目录明确标为 `PARTIAL_READ_ONLY_BACKUP_NOT_EXECUTION_ROOT`，保存的binding仍指原根，不初始化或消费新账本。没有改原请求身份、恢复机会、计数或结果。只读副本中的原回答有效不等于真实模型又成功一次；不拿单组恢复代替六组Enphase公司验收。

这是一个真实D04原调用/来源恢复样本，不再只有普通结果小状态。但它不包含其他97条D04调用和其余非D04历史，不是完整十家公司AI/来源/账本/安装副本备份，更不是异机或离线灾难恢复承诺。待补完整备份及现成公司入口适用核验的责任仍保留。

## 重现

使用对应程序根的Python路径，来源及原账本只读、输出另选新目录：

```sh
PYTHONPATH=/path/to/program/scripts python3 inspect_saved_responses.py \
  --ledger-root /path/to/original-ledger \
  --source-root /path/to/original-ledger/source-inputs \
  --output /path/to/new/inventory.json
PYTHONPATH=/path/to/program/scripts python3 restore_reader.py \
  --backup-root /path/to/partial-read-only-backup
```

程序只禁外部网络；JSON读取、哈希核对和当前响应检查走真实实现。恢复所需原回答、tar和SEC正文留本机私有目录，不重复提交原大档案。`restored-sample.json`及 `restore-reader.log`保存本次实际读证据。当前check通过、原成功、可被某次公司任务消费和正式接受四层不能互换。

# Paramount D04：既有真实响应进入当前普通更新

本项只核对原第179—188次已成功的Paramount D04响应在当前`task/b06-new-source`绑定下能否由普通更新入口形成可保存的FY2025候选。没有重发模型或SEC请求，也不重做原D04完整公司演练；隔离状态根为`/private/tmp/issue28-d04-paramount-normal-77f-20260928`，来源为#28原账本`source-inputs`，不是生产状态根。

`run-existing-real.py`在当前V14执行权限及接线收据有效后，使用原CallLedger、禁网与限制子进程的普通`run_company(metric_ids=['D04'], native_assessment_mode='LIVE')`。实际`run.log`返回`UPDATES_READY / CANDIDATE_READY`；当前Run ID为`run:ordinary-integrated:5a2940f237641f39797779c4a8660b43cfc97d8548f2081ff44d4fc12f886636`，Result ID仍为原完成收据的`sha256:a185d849dd9fd9d04fee0ac593b4028fd60715d51b7a67b7b1067ab7c544ee58`。公开行仍为Paramount FY2025 `TEXT_QUAL`、空数值、`D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`；这只表达规定范围内未见相应披露，不是财务健康保证。当前输入登记ID随需求闭包变化，不改签原输入或原Run。

`verify-raw-identity.py`从当前Run绑定定位安装的schema2登记，对照原固定账本十个调用目录：179—188各条来源、请求、intent、terminal、wire的**JSON解析内容**相同，助手正文与原`wire/assistant-output.bin`逐字节相同，原始HTTP响应文件哈希与原wire记录一致，请求ID/摘要与原批次摘要一致。`raw-identity.json`保存十条序号、身份和哈希；它不声称本轮更新前后原调用目录或旧私有Run的整树哈希均已采样。

`cold-read.py`在独立进程中从本次Run的**安装代码与来源副本**重验Result、需求闭包和公开行SHA；`cold-result.json`为`PASS_INDEPENDENT_INSTALLED_RUNTIME_COLD_READ`，私有历史当时已有810个文件前后哈希一致、变化0、网络尝试0。交接时意外已有一轮相同只读冷读在运行，启动本轮后发现重叠；两轮均通过，保留最终日志和收据，不能把重复运行说成必要的新业务证明。未在这两次只读回读期间修改私有历史。

`repeat-existing-real.py`在同一私有状态根重复触发，实际`repeat.log`返回`UPDATES_READY / NO_SOURCE_CONTENT_CHANGE`，耗时723.996秒。重复尝试有自己的终态，但成功指针仍指向第一次当前Run，`new_candidate_created=false`；该成功包前后整树哈希不变，Result ID不变，总账计数仍143/143/52、195行。`reconcile.py`只读原完成与原冷读摘要及本次更新、冷读、逐条原始身份、重复触发收据，`reconciliation.json`对账通过：原Run与当前Run身份不同，Result ID相同；原第179—188次无新增调用信用。此处没有通过重复触发创建第三个Run或购买回答。

本项新增的是**第二家已有真实D04公司结果进入当前普通更新入口**的限定证据；D04原10/10候选数量、390当前坐标信用均不增加，不证明新财年在线更新、正式采纳、生产切换或全部旧入口退出。原账本在本次首次更新前后均为143/143/52、195行，调用目录名及binding、claims、来源请求日志、active指针哨兵哈希不变；新增真实provider/paid/SEC为0/0/0。#47/PR52的分支、运行根、账本和权限没有使用。

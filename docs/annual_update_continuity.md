# 受限年度连续更新

本入口限定 Marriott B01/B10、连续主体、完整自然年度普通10-K。B01 Revenue与B10全球、可比、全系统物业含义不变。实现复用原生候选执行、Evidence/SYSTEM Review/Calculator、完整Projector、PublicationView和原生切换日志。新规则是 `annual_candidate_adoption_v3`、`issue_28_v8`/V9；旧v1/v2文件与历史执行不改。本轮实际生产根只读，规则内容与真实阶段许可分开，代码存在不代表已完成两次真实执行或持续生产授权。

## 三个进度位置

`annual_update`分别输出发现的申报、已有候选、已发布版本。`candidate_work`回答是否还需计算，`publication_work`回答是否还有候选等待发布。清单检查失败仍保留此前已知待发布事实；未提供发布基线不是“没有待发布工作”。同年但原Run不同也不能只按显示数字宣称相同执行。

`PublicationView.native_result()`从当前年度包的采纳绑定读取B01/B10原生记录；继承只沿明确的前驱关系寻找，不能因当前表布局不同一律退回R3。老R3只嵌入其delta原生Run：B10可回读，R3中未嵌入的B01/B03原生内容明确报不可用，不从公共CSV或外部猜一个Run。旧完整公共结果与证据仍可读取。

## 正常入口

```text
python3 tools/vnext_annual_continuity.py initialize-data --data-root <外部来源目录> --output-json <新记录>
python3 tools/vnext_annual_continuity.py stage-proposal --help
python3 tools/vnext_annual_continuity.py run-once --approval-url <真实阶段评论URL> --output-json <新记录>
python3 tools/vnext_annual_continuity.py close-stage --approval-url <同一URL> --output-json <新记录>
```

initialize-data只复制已有完整原文、真实request ledger/headers与必要规则，不联网。阶段提案固定受审实现和测试身份、独立审阅、外部来源/运行/预算/发布根、真实历史起点、期间范围与最长七天期限。提案自身不授权。实际账户在GitHub代登记时应另行说明用户委托与隔离用途；运行使用原 `_github` 边界回读作者、正文、时间、编辑状态与绑定。

一次run-once先检查同笔未完成事务和已成功待发布候选，再判断新输入；只有确无工作才返回NO_CHANGE。每份输入的计划、请求、原生Run、使用量、完整包及精确前驱由程序生成。B01/B10不齐全不前移完整成功引用和active；原B03附带记录不删除、不误采纳。

阶段固定预算为正常不同年度模型请求最多2次、另一个有根因修复/离线回归/独立复核的条件名额，总provider/paid不超过3/3，SEC不超过6，零重试。永久预算注册、逐请求预留及WB-3实际终态分别记录；新进程或输入目录不能重置。UNKNOWN与失败不能写成零。缺凭据先报告，不消费模型预留。交付时关闭阶段，未用额度不转入后续任务。

## 两轮历史材料验证

历史S0由真实旧B01原生结果与已提交的旧B10资格Run只读重放构成，明确只是新建隔离起点。原B01 OPEN/NOT_RUN和B10 FROZEN/PASSED状态保持不变；其他238坐标保留各自期间。普通后续更新禁止期间回退。

历史可见性是外部输入边界中的 `SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY`，只含as_of_utc。程序从完整原始清单筛出当时可见的申报，仍走同一选择/DEI/context检查。原SEC字节、请求行、headers不改，另记derived visibility receipt；不能称为新的在线清单。运行参数不接受年度答案、accession、表格、单元格或数值。

S1完整继承S0，S2完整继承S1。每份请求的来源/期间/Run/执行和对应前驱均精确绑定，不能在冲突时偷偷重设前驱。新包仍为2项采纳+238项继承/327公开行，模型不为未变指标重算。来源不足或未知范围需要停止相关结果，而不是生成器自报PASS。

## 有限触发与停止

```text
python3 tools/vnext_annual_continuity.py trigger --approval-url <同一URL> --max-invocations 2 --interval-seconds 1 --output-json <新记录>
python3 tools/vnext_annual_continuity.py stop-trigger --approval-url <同一URL> --output-json <新记录>
python3 tools/vnext_annual_continuity.py trigger-status --approval-url <同一URL> --output-json <新记录>
```

触发适配是有限前台进程，最多3次，直接调用同一个run-once CLI。没有安装生产定时器、后台队列或守护平台。停止只阻止后续触发，不强杀已发出的模型请求；该次按原生终态记账。每次输出和日志在阶段trigger目录，结束后running=false。异常退出先看原预算和候选/intent，不创建另一目录重新获得调用机会。

## 证据边界

短边界测试进入fast白名单，完整包/原始材料另作受保护集成。真实provider执行、保存响应回放、外部I/O模拟与在线SEC获取分别计账。独立模型的两次原文核对属于本工作包验收，不是未来所有未见材料资格。

当前实际生产包是PR40已发布的FY2025版本。本工作包不切实际active、不自动合并新PR。两轮连续更新、重入、失败、预算与有限触发验收后即收口审核，下一项进入R5有限迁移，并逐批证明不靠旧语义生产或补数，不无限打磨Marriott。

<!-- capability-anchor: CAPABILITY.annual_update_continuity -->

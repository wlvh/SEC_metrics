# 分开发生日期与披露状态

v4分离event_dates/reported_status；slot42已把私人继续识别为ONGOING且不推开始日期，但将月度日期规范为ISO形式，旧v4要求原文日期，故D03_EVENT_DATE_FORMAT失败；仍漏3个标题索引。旧失败不按后继规则改判。

所有offline-wiring包中的新执行是MOCK，部分包另保留标明身份的历史LIVE提议作为只读测试输入。还原/引用核验不创建新调用或正式信用。模型Key不在包或仓库中。来源/调用/首次失败按原版本保存，当前总账及后继入口见../execution-state.json和../continuation.md。

恢复沿用../ordinary-document-identity/restore-document-material.py：在新外部临时目录中，将所选*-index.json复制为material-index.json，链接对应tar.gz，再使用--evidence、--repository、--output参数。每个包的索引记录对象SHA和原路径，不能把恢复的数据升级为新获取。

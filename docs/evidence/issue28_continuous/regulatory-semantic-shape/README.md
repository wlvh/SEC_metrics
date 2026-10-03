# 明确响应类型

D03v2增加实际JSON字段类型和必评项说明。真实slot39覆盖全部必评项，但把原文小写in改成In，严格引用校验拒绝。原响应和旧v1/v2保留。

所有offline-wiring包中的新执行是MOCK，部分包另保留标明身份的历史LIVE提议作为只读测试输入。还原/引用核验不创建新调用或正式信用。模型Key不在包或仓库中。来源/调用/首次失败按原版本保存，当前总账及后继入口见../execution-state.json和../continuation.md。

恢复沿用../ordinary-document-identity/restore-document-material.py：在新外部临时目录中，将所选*-index.json复制为material-index.json，链接对应tar.gz，再使用--evidence、--repository、--output参数。每个包的索引记录对象SHA和原路径，不能把恢复的数据升级为新获取。

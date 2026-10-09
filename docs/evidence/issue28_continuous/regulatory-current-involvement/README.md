# 修正总体当前披露与上下文重叠

当前v6不要求披露具体案名才能承认明确的当前调查/执法涉入；context_only_source_indices必须与finding引用互斥。修后JPM执行和后续验收以实际新增证据为准，不能提前报通过。

所有offline-wiring包中的新执行是MOCK，部分包另保留标明身份的历史LIVE提议作为只读测试输入。还原/引用核验不创建新调用或正式信用。模型Key不在包或仓库中。来源/调用/首次失败按原版本保存，当前总账及后继入口见../execution-state.json和../continuation.md。

恢复沿用../ordinary-document-identity/restore-document-material.py：在新外部临时目录中，将所选*-index.json复制为material-index.json，链接对应tar.gz，再使用--evidence、--repository、--output参数。每个包的索引记录对象SHA和原路径，不能把恢复的数据升级为新获取。

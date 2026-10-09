# 单独内容核验

读取原始slot40响应作为明确绑定输入，原终态证据逐项重算。slot41检查14提议并拒绝5个标题错误，但未纠正私人继续的时间字段。最初环境修复行政和解的测试预期过宽，原预期与修正均保留。模型内容检查不是独立代码审阅或正式Review。

所有offline-wiring包中的新执行是MOCK，部分包另保留标明身份的历史LIVE提议作为只读测试输入。还原/引用核验不创建新调用或正式信用。模型Key不在包或仓库中。来源/调用/首次失败按原版本保存，当前总账及后继入口见../execution-state.json和../continuation.md。

恢复沿用../ordinary-document-identity/restore-document-material.py：在新外部临时目录中，将所选*-index.json复制为material-index.json，链接对应tar.gz，再使用--evidence、--repository、--output参数。每个包的索引记录对象SHA和原路径，不能把恢复的数据升级为新获取。

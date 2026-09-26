# 来源选择与原文重建

v3让模型选择来源索引，由程序提取完整原文，原响应单独保存。slot40引用通过但标题分类及时间仍错。provider-observations包保留38–40，continued-provider-observations保留41–45；逐对象SHA已解包核验。这里只证明来源/格式，不能代替语义。

所有offline-wiring包中的新执行是MOCK，部分包另保留标明身份的历史LIVE提议作为只读测试输入。还原/引用核验不创建新调用或正式信用。模型Key不在包或仓库中。来源/调用/首次失败按原版本保存，当前总账及后继入口见../execution-state.json和../continuation.md。

恢复沿用../ordinary-document-identity/restore-document-material.py：在新外部临时目录中，将所选*-index.json复制为material-index.json，链接对应tar.gz，再使用--evidence、--repository、--output参数。每个包的索引记录对象SHA和原路径，不能把恢复的数据升级为新获取。

# 首次D03接线与执行清单补齐

D03v1复用完整原件并沿原opener/WB-3留MOCK材料；真实slot38返回有意义的历史日期/私人继续信息，但unresolved类型错误及遗漏使校验失败。historical-binding-gap.json登记最初六次D04缺少8个源码/规则的执行绑定；补充字节按48d73/210重取且source.module_sha256匹配，不重签原slot，不追授信用。

所有offline-wiring包中的新执行是MOCK，部分包另保留标明身份的历史LIVE提议作为只读测试输入。还原/引用核验不创建新调用或正式信用。模型Key不在包或仓库中。来源/调用/首次失败按原版本保存，当前总账及后继入口见../execution-state.json和../continuation.md。

恢复沿用../ordinary-document-identity/restore-document-material.py：在新外部临时目录中，将所选*-index.json复制为material-index.json，链接对应tar.gz，再使用--evidence、--repository、--output参数。每个包的索引记录对象SHA和原路径，不能把恢复的数据升级为新获取。

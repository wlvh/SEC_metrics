# D04 两份真实候选进入当前完整版本准备的版本边界

在已推送 `a863f722` 的产品代码树上，`prepare_private.py`选取现有 Enphase 与 Paramount D04 普通更新成功尝试的原生 Run、安装数据及真实响应身份，尝试经现有 `ordinary_release_preparation.prepare()`生成一份私有多坐标版本。两份输入原本各自为`CANDIDATE_READY`，完整来源审阅标记为真，Result仍为`WITHHELD`并由原D04限定范围规则投影为`TEXT_QUAL`。本次没有重发模型或SEC请求、没有改写原调用或提交生产操作。

**实际结果为失败，未形成新的完整版本。** `run_prepare.zsh`以nohup执行、`prepare.exit=1`；`prepare.log`显示准备器在第一份原生Run的`_mechanically_replay_open_run()`中被现行需求加载器拒绝：`Run Requirement Snapshot is invalid`，具体为`Continuous successor installed snapshot differs: baseline_manifest.json`。错误发生在组合矩阵及公开行之前，因此没有新的私有Publication、390坐标信用或冷读成功。私有输出根`/private/tmp/issue28-d04-unified-release-a863-20260928`是未完成的复制材料，不能作为已准备版本使用；本轮不删除或重新签署它。

`binding_diff.py`和`binding-diff.json`只比较这两份安装输入与当前代码根的V14清单。两份旧Run的baseline SHA-256相同，为`345712f3…`；当前head为`8258cf4e…`。父级声明未变，但七个执行文件绑定与三个规则文件绑定不同，包含D03新路线及共享原生收据组件。这证明了**安装时代码身份不同**，不证明所有D04语义都已改变，也不能据此让当前加载器忽略清单差异。旧Run既有独立冷读证据保持原范围；本次没有执行前后整树哈希，故不声称再次逐字节重验旧Run。

下一步在确定的当前实现下，从原已成功D04响应零新调用构建当前绑定的原生Run，再走同一完整版本准备与独立冷读；如果实际需要跨版本直接选择旧Run，须另有能认证旧安装代码及其相关语义的显式兼容路径，不能让自签旧包任意执行或取消当前快照断言。这里记录的是一个真实集成阻断，不是D04十家公司原候选失效，也不是要求重新购买模型回答。`prepare_private.py`与`run_prepare.zsh`是这次失败的可复核入口；未运行独立冷读。原账本真实新增调用0/0/0，生产、#47分支及PR52均未操作。

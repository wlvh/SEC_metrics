# D01 保存来源测试进入正确的 CI 时限层

`eea7821c` 对应主 CI `36966491013` 终态 **failure**：fast 作业145 个选择器里唯一失败的是 `tests.vnext.test_d01_emphasis_successor`，30.014秒碰每选择器30秒上限，返回码124；该作业没有报告D01业务断言失败。`remote-fast-failure.json`从已完成 job `110711265166` 的结构化输出提取这条确切失败与其余144项成功；其余15个主CI作业最终均成功。

这条fast选择器此前把两家公司完整保存原件的候选与Evidence重建也放在30秒短测内。本补丁仅分离测试层：fast 模块保留无需大原件的标点桥接、下划线、已知跨页未支持及单数字不误合反例；两家真实保存原件、原生候选/Evidence、默认旧路径和原始字节篡改拒绝搬到`test_d01_emphasis_material.py`，只在 `SOURCE_TESTS` 列表末尾追加该选择器，适用现有240秒来源材料限时。`tools/run_fast_tests_v2.py`的运行函数、其它超时、旧选择器与产品源码均不改；不是跳过原件，也不是盲目提高fast上限。

`verify_split.py`分别通过实际runner执行完整fast套件及只含新D01材料入口的来源分片，记录选择器数、各自耗时和限时。首次脚本误对fast套件使用不支持的分片参数，`selector-split-initial-error.log`保留工具层失败；修后按真实runner规则执行。此目录没有真实SEC/模型调用，不改变原D01私有Result、内容审阅或390信用。修后新head远端CI仍须另行按实际终态验收。

修后本地日志`selector-split.json`记录完整fast **145/145选择器通过**，其中D01短测0.087秒；保存原件层的两项D01测试14.161秒通过，均低于各自30/240秒限时。`selector-split.exit`为0。分层只改变测试运行位置，不改变D01产品源码、需求身份或既有两份私有Run的`NOT_RUN`发布验证状态。共享影响限于在`SOURCE_TESTS`列表末尾追加一个选择器，#47堆叠分支接入时应核对自身CI选择器总数。

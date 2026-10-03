# B13 V6：独立审阅发现与修后收口

**限定审阅结论：已发现的普通更新V5/V6合同错配修复并独立复验通过；本次差异无剩余发现。** 这不是全PR批准、旧6e5/D03受限审阅的替代或LIVE B13暂停解除。

## 原发现与版本

`edbc-review.md`完整保留对补丁SHA `edbc9385404aad8048bd3f0a2b4e87c336efc4c1b078c44d7d342fa7b37dc52f`的原审阅。`result.json`保存确认反例：实际ensure_native_update选择旧V5 options，普通_config选择V6，准备和消费不一致。原发现没有改成通过记录。原生角色部分另有8方法及16个独立正反例，含真正合成原HTML→native parser→Candidate/Evidence、原件Calculator0.8及未决拒绝；均非真实模型信用。

修复补丁SHA为`4e9428ce69b4ab8298e35ac98116fa68bbc549afe20d3336fed2a7ba8b704b34`。增量只有三个协调模块和对应测试：新增`current_registered_update_options`，普通_config与ensure_native_update统一从它选当前合同；低层旧factory默认V5，旧已登记输入仍按其显式身份解释。语义量角色、prompt、schema、原件重算及接收器文件没有随此修复再改，见`repair-version-check.json`。

## 独立复验

- `repair_probe.py`用同一13情景重跑，原错配变为确切MATCH；完整合成来源Candidate/Evidence、Calculator正例及篡改/漏unit负例仍通过。原probe.py/result.json和初始辅助测试误预期日志保留。
- 独立运行新增`test_finite_refresh_preparation_and_run_share_current_native_contract`通过，0.013秒。执行实际refresh协调器→ensure→_config，B13与D04两路准备/消费options一致。source/session/登记边界及run_company是明确double，不能将测试返回的UPDATES_READY当作完整原生Run成功。
- 低层V5默认保持；当前B13选择V6，D04原complete响应合同保持；LIVE集合仍仅D04。原固定总账、有限上限、原收据/失败、源准入及0自动重试无增量放宽。

作者最新format提示的六请求recorded→登记→Run/公共行255.299秒及随后冷读、当前重登记各有其版本证据。本次未重复大材料运行，也没有把作者这些记录改称本审阅的完整新输入Run。修复后的主分支统一绑定、必要实际验证及Issue整体交付仍由根任务继续。

审阅者没有实现被审合同或修复，没有apply主分支；新增provider/paid/SEC为0/0/0，无真实公司结果或390完成信用。

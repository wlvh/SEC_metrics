# B13/D04 复用既有普通更新历史：待应用补丁

运行补丁保存在 `/tmp/sec_metrics_issue28_continuous/native-update-integration.patch`，本目录初始探针完成后，桥接及后续source/runtime规则修复已由根应用到主工作区，并继续进行完整生命周期验证；本目录保留原未应用时的测量身份。本项不建立新历史控制器、不接通 D03、不执行 provider/SEC、不授生产信用。

## 现有链的有限改动

- `normal_run_v3` 的既有 B13/D04→`capacity_run` 分派继续使用。更新集合只增加 B13/D04；原36配置/描述字节形状不变，8家结构性 B13 不用模型解释参数。
- 原 `ordinary_update_cycle` 仍按指标记录成功、失败、恢复和重复触发。仅已登记原生输入增加 source_id、input_record_id、assessment_set_id、模式及请求合同身份；相同原文而有效解释改变不能误判无变化。native 单指标历史使用真实 V14 闭包。
- 严格的 B13/D04 定义域无披露分支复用真实 `project_defined_absence` 和完整 Run 重放，不把任意 WITHHELD、未知关系、实现不支持或不完整集合当成功。
- `prepare_requests` 增加有限 `source_root` + 创建者拥有的 ledger 参数；仅普通 B13/D04 来源可选。LIVE 只允许当前 ROOT/固定 source-inputs 和固定总账，记录测试必须给原 factory-owned recorded ledger。旧默认/历史control保持原义。结构性 B13 的显式当前准备也从 ROOT 读取规则，原件仍来自 source root；实际 fixed source-inputs 的 Pfizer FY2025 已返回 N_A_STRUCTURAL、无 assessment、0调用。来源工厂沿 going_concern→r6→capacity 显式调用现有 ordinary source admission，不把规则树塞入不可变来源目录。
- 新 `capacity_update_input` 只读扫描该公司/指标原 SUCCEEDED 来源集合，逐原请求、响应、收据及当前 acceptor 重验，唯一完整集合才自动0调用重新登记。它只接受完整 units/documents、原件URL/内容hash集合、选择期间和所有实质请求字段一致；允许有限 acquisition 元数据改变，原 provider source/request/response/receipt 字节不改。重放对象禁止 execute。
- 新 schema2 注册记录保存原 source snapshot，供现有 `capacity_run` 安装与包内重算使用；旧 schema1 及旧导出默认不改变。准备时规则来自当前 ROOT，重放时规则来自已安装运行包。当前来源等价证明从 case 单独返回，不参与无变化描述身份。

## 已实测

1. 原完整 Enphase recorded 夹具在新闭包下会查不到原登记；同body新attempt复制件也会改变 semantic_source_id，但完整原件内容、units/documents相同，仅 source_id/request_id 变化。原来源路径在旧 final going_concern admission 处失败，材料见 actual-native-input-probe.json。
2. 原有 register 函数可用6个原成功收据在当前闭包0调用重登记，原账本文件不变；见 reregister-probe.json。
3. **新桥接已在同body新attempt复制件通过6请求完整重验与schema2重新登记，388.073秒，原 recorded ledger 全部文件hash不变，0/0/0。** 见 bridge-material-result.json、bridge-material-third.log。该次使用隔离未应用模块和当前 ROOT 绑定，是工程接线探针，不是已绑定原生更新验收。
4. 8项短测试0.061秒通过：旧配置保留、当前native闭包、输入身份改变、固定分派、结构性范围、精确同内容证明、假ledger/重放对象禁止执行，以及真实专用无披露检查。见 extended-unit-tests-final.log。

第一次桥接根路径别名拒绝和第二次schema2字段漏接KeyError均保留；后者在原6收据重验后、检查返回snapshot时失败，不能算成功。

## 仍须完成

根已进行应用及绑定，继续运行已新增的 `RegisteredNativeUpdateMaterialTest`：完整来源进入原 native Run、重复触发、损坏保留、恢复和历史读取。它尚未执行，不能把本补丁/注册探针当作正常更新完成。还应以samebody新attempt加入实际生命周期对照，核对 NO_SOURCE_CONTENT_CHANGE；当前只证明其能够自动重登记。

更新检查发现实际新来源/新实质请求但没有完整原成功集合时仍明确失败/待验证，不新发模型抽样。真正新普通 B13/D04 执行已有本补丁的有限 source-root request 工厂入口，自动模型任务安排仍沿已有调用政策进行，不由更新JSON授信用。

本项新增完整真实公司—指标结果0；provider/paid/SEC新增0/0/0。没有改固定总账、实际source-inputs或旧68/82/94终态。

# B13 V6 定向独立差异审阅

审阅者request_counting未实施本次B13程序数量职责合同。审阅对象为`b13-program-v6.patch` SHA `edbc9385404aad8048bd3f0a2b4e87c336efc4c1b078c44d7d342fa7b37dc52f`及其隔离workspace，14/14补丁文件实际SHA核对相符（version-check.json）。这不是受限6e5/D03子任务的重启，也不是全PR批准、真实结果信用或LIVE暂停解除。

## 一个已实测的接线发现

**正常B13有限新请求准备仍选V5，普通Run已选V6。** `capacity_update_input.ensure_native_update`第149行调用`registered_update_options`未传`program_quantity_roles`，所以采用旧默认；`ordinary_update_cycle._config`显式传True。真实协调器两端产生不同options。有限新请求准备和末尾登记都复用这个旧options，因此后续普通Run不能消费刚准备的同一合同。LIVE B13暂停仍生效，所以没有据此声称已经越权发真实请求。

`probe.py`使用实际ensure_native_update和_config，仅将prepare_registered_update替换为记录参数的边界double；输出result.json最后一项保存确切两份options和不一致结果。它证明实现接线不一致，不冒充实际模型执行或失败的完整Run。作者已获通知，待补丁修复后复验。

## 实际检查与正反例

- 独立重跑作者8方法短套件PASS，日志上级independent-request-counting-program-tests.log。旧V5 factory默认身份保持；新合同身份明确不同。
- `probe.py`前12情景：合法完整合成source的程序产量80、可用产能100经真实build_acceptance生成Candidate/Evidence PASS；原件重算Calculator输出0.8。缺unit、重复unit、reviewed=false、模型擅自返回ACTUAL_PRODUCTION/AVAILABLE_CAPACITY、重签移除contract/version、改source原文但保留原raw均拒绝。
- 合法模型OTHER_CONTEXT冗余引用不抹掉程序的原量proof，两种量仍存在，原Calculator仍为0.8。最初测试误预期此冗余标签必须拒绝，导致探针AssertionError；已核对正确行为并保留probe-first-assumption.log。这不是业务错误接受。
- `native_probe.py`从明确合成的原始HTML经真实_native_units解析，保留全部DEI、contexts、原native序号及source units：ProductionQuantity整数事实被模型按合法原ordinal标OTHER_CONTEXT，仍具体报IMPLEMENTATION_UNSUPPORTED并阻止acceptance；continuation原文内数量同样不能被空响应抹除。USD借款额度经原namespace/单位证明为非物理量后，不要求模型重复确认，但所有units仍须回复，Candidate/Evidence PASS。
- 上述原生parser探针是合成原件构建+实际来源解析+实际acceptor，不具有获取准入、真实公司或真实模型信用；没有把最小factory材料冒充完整已注册公司输入。

## 代码阅读边界

程序角色从完整source单位重算，再按当前请求分组划分；模型finding与程序finding合并前后都保留原必评引用集合检查。非物理native角色只承担自己的原引用；native物理量与supplement数量实现不支持时进入具体未决，不变成未披露。所有单位仍由原response完整集合检查覆盖。

Candidate/Evidence保存程序proof。登记沿既有factory-owned ledger、固定LIVE root、原收据当前replay；export额外version必须与source一致，私有登记比较保持。prepare_case与文字构建路径在原source/raw重建后调用verify_original_program_assessment；单独quantity_contract或original_program_records并不独自授来源真实性/登记权。

V6的源字段、policySHA、响应schema、程序contract均进入请求及digest，旧V5默认保留。没有改200000上下文、8MiB、120秒、4096输出预留、零重试或固定总账。ordinary有限调用仍只允许D04 LIVE，B13暂停和D03未启用保持。正常协调器合同错配是本次唯一确认发现。

## 完整材料只按实际版本读取

作者最新format提示6请求recorded→登记→安装→Run/公共行记录位于`material-format.log`和`material-enphase-format/summary.json`，255.299秒，Result d4714a55…，公共notes明确recorded、非真实模型信用。独立审阅读了该当前记录，没有重跑整套或声称修后协调器已由它覆盖。旧material-enphase以及其攻击日志按其旧提示身份解释，不能升级为format修后Run证明。

旧82/94实测原请求一致性材料`v5-bytes-result.json`属于作者已有证据，保留原FAILED。当前计数材料列Ford11/Enphase6及完整上下文；这些不是执行信用，本审阅也没有重新进行调用优化。

新增provider/paid/SEC均为0；未修改主runtime、固定source/ledger或原receipt。完整Issue责任及原权限保持。

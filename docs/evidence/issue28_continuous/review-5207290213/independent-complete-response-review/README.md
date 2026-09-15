# 第69次之后：D04完整响应合同限定独立审阅

审阅者未实施本次响应合同变化。范围仅为v5提示/响应协议、`COMPLETE_RESPONSE_VERSION`及动态schema/checklist、显式工厂选择、登记/Run恢复的`response_contract_version`、对应D04测试和CLI/native环境选择。确切文件SHA及基线HEAD见`scope-files.json`。不覆盖本审阅者此前实施的计数/分组，不覆盖6e5 D03来源事实旧受限审阅，不是用户本人审阅、全PR批准或真实路线资格证明。

## 结论与实际发现

本范围当前未发现未处理的阻断。首次独立探针发现一项真实合同不一致：新提示要求按清单顺序返回，但完整三单元反序响应仍获接受。没有遗漏单元或假无披露输出。根执行者已仅在v5增加响应unit_id列表与必答清单的顺序相等检查；复验反序明确拒绝、完整正例仍通过。新政策元数据也已明确为schema_version5、独立policy_id、supersedes v4。旧v4文件与基线HEAD逐字节相同。

## 定向反例

- 完整三单元正例通过；漏单元、重复单元及反序单元均拒绝。
- 调用方重签并缩小schema的min/max、unit enum、required_response_unit_ids或checklist，均报`D04_NATIVE_REQUEST_POLICY_CHANGED`。
- 错版本报`D04_RESPONSE_CONTRACT_VERSION_UNSUPPORTED`；只删版本而保留新合同字段不能降级为v4。
- 删除必评候选并同步删checklist后，原明确疑虑仍被来源断言检查拒绝，不能取得无披露结果。
- 同时缩小请求本身及其schema/checklist的自洽字典，只能说明该字典声称的局部范围。使用未缩小完整source的真实`SemanticRequest.validate`成员检查会拒绝`CONTINUOUS_REQUEST_NOT_IN_SOURCE`。此工厂测试明确模拟来源准入、进程能力检查和transport policy读取；没有模拟请求成员检查，也没有获取来源或执行信用。

登记字段由工厂来源写入并参与登记身份。Run从导出提示选择唯一支持版本后，仍重验私有/安装信任记录、source_id、输入身份、完整原请求及接受记录；B13适用路线禁止借用D04合同。旧来源缺版本字段时沿原v4路径。CLI与完整native测试均明确传递选择参数；历史v4记录不补新字段。

## 原69及验证边界

原69在旧v4要求5个单元、实际只回应2个。使用其原请求与未改原响应，当前旧路径仍拒绝`D04_RESPONSE_UNIT_SET_INCOMPLETE`，原终态没有改写。另一次**离线拒绝探针**仅将该原响应的request_id换成新合同对应请求ID，仍因缺单元被拒；`original69-result.json`明确禁止复用执行信用，并保存原source、request、原始响应、assistant输出和terminal的未变SHA。

最终18项D04测试在本审阅进程通过（0.301秒）；独立定向反例结果、原69离线拒绝及工厂成员边界在相邻JSON/日志。工厂测试工具最初分别遗漏合成source_proofs及使用了非工厂规范序列化，触发早期拒绝；修正测试工具后基线通过、成员攻击拒绝，初错日志保留。这些不是产品错误接受。

本次新增provider/paid/SEC为0/0/0。尚未观察模型在新合同下完成全部单元；后续必须使用本版本绑定的必要真实验证，原69失败或离线改ID测试不能成为新执行信用。完整原生登记/Run/公共行/冷读由根任务按当前实现另外核验，本报告不把18项短测试当作完整实时结果。

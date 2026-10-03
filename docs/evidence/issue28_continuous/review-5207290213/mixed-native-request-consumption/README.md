# 同一原来源集合的精确混合请求消费

本工程子项只修改现有集合收集、登记重读和文字范围构造三处，消费根执行者提供的`native_unit_index`接口；不修改来源分组、D04语义检查、模型调用入口、原始请求或账本。

## 变化

- `collect_native_assessments`按照prepared实际请求顺序，要求`validate_request_partition`逐一匹配同一完整来源的原分组。每组只能选择确切BASE或确切INDEXED_UNITS_V1，不能漏组、重复、调换组或借用其他source。
- 仅存在INDEXED请求时，集合记录才增加`native_request_variants`。全BASE保留旧无字段记录形态。
- `load_registered_input`与`capacity_text_results._prepare`按该名册重建每份原请求，然后继续现有原HTTP请求hash、原始输出、plan、terminal、acceptance receipt及当前来源检查。改变响应合同的请求使用自己的新收据；已成功BASE请求不转换、不重签。
- 已失败BASE请求可以作为历史保留，而新INDEXED请求独立完成同一原分组；历史失败没有获得当前成功信用。

该设计使原70一类的有效原成功可与后续修复请求共同完成原完整来源任务。**本子项没有操作或重新签署真实70/71，也不以测试替代根任务对真实原收据的复验。**

## 验证

`test_native_request_variants`使用三份具有完整原件身份格式的合成年报/修订，形成三个原来源组；组合BASE / INDEXED / BASE。

- 正向经过实际D04 acceptor、完整Candidate/Evidence、真正acceptance receipt生成与原校验器、集合收集、登记加载、文字完整范围构造。
- 逐个原receipt仍调用原`control._validate_acceptance_receipt`，第一份BASE的body和receipt保持相同；测试账本原请求及终态文件前后逐字节不变。
- 保存的失败BASE组仍在测试文件中，只有对应新INDEXED成功参与选定名册；没有把原失败重标成功。
- 漏组、重复组、调换顺序、跨source、短名册及错版本均拒绝；将混合集合重签为全BASE，登记重读和文字范围构造均拒绝。
- 全BASE集合不新增变体字段，并按原请求名册重建。

归档运行时读取、测试账本snapshot和私有journal位置是明确test doubles；来源、plan和响应均为合成材料。请求分组匹配、响应校验、Candidate/Evidence及完整acceptance receipt校验、登记字段/原body校验、文字范围构造没有模拟。没有真实SEC/model执行信用或新公司—指标结果。

首次3项通过（0.068秒）。补入登记重签反例和原receipt校验调用检查后，加既有18项D04回归共21项通过（0.353秒）。日志及具体实现SHA在本目录。根执行者另做本子项审阅、当前完整执行绑定和真实原身份复验；此处不是自我独立批准。

新增provider/paid/SEC为0/0/0，无生产、合并或active权限。

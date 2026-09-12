# C02/D02 最小来源依赖与既存不可变凭据核对

本阶段只读源码、原始请求记录和已保存发布包；没有修改输入适配层、旧来源函数、请求类别、attempt 或结果。provider/paid/SEC = 0/0/0。

## 结论

沿完整 governance 准备带入的292个请求证明，并不都是 C02/D02 的业务依赖。保留不变的 `normal_annual_input.prepare_saved_annual_input` 时，C02 每公司4项、十公司40项，D02每公司3项、十公司30项；二者并集40项，含31个 IMMUTABLE_ATTEMPT、9个原类别 LEGACY proxy。可以退出252个正文/索引/分片依赖，包含228个 LEGACY，不能仅在返回记录末尾删掉它们，必须改变后继输入准备的实际调用及绑定范围。

## 按实际调用与字段界定

| 来源 | 当前数量 | C02/D02消费事实 | 后继处理 |
|---|---:|---|---|
| current submissions | 10 | `normal_annual_input.select_filing` 核对 CIK、recent 完整列、latest ordinary reportDate、amendments；检查完整 files 列表及 filingFrom/filingTo。C02还用同一 recent 的DEF14A/DEF14A-A/10-K-A及acceptance时间唯一选源 | 必须保留完整原JSON，不能裁成命中行 |
| ordinary annual HTML | 10 | `annual_period` 从DEI与context核对主体、实际期间、FY、AmendmentFlag；v2对C02用作年度分组锚，对D02解析原文/附注/事实 | 必须保留 |
| companyfacts | 10 | 现有不变annual adapter实际读取并验证根CIK；不消费财务金额生成C02/D02 | 为复用原API保留；不能假装未调用 |
| governance source | 10 | 九份当前同CIK DEF14A、一份同期间Part III 10-K/A；C02解析完整支持陈述，Part III由原文结构证明 | C02保留；D02不用其正文 |
| 8-K primary/header | 103+102 | 仅normal_governance的C04 event_input/source-set路线；C02/D02不计算事件，也不以它们证明当前proxy或annual选择 | 不再调用/获取，不再绑定 |
| accession index/auditor XML | 19+19 | 仅C04 current/prior auditor_filing搜索与auditor fact来源 | 不再调用/获取，不再绑定 |
| history JSON bodies | 7 | 完整governance为同CIK prior与年度事件范围而读取；当前十家公司annual门已经证明各shard filingTo严格早于当前年度结束日 | 当前C02/D02可不读取正文，但current JSON的完整分片声明必须保留并验证 |
| 另外 target_primary | 2 | Southwest早于当前proxy的annual amendment正文、额外prior HTML；选择时间/修订状态由current metadata证明，D02不宣称修订处理已完成 | 当前两指标不必载入其正文 |

这里的“4项/3项”是保留年度准备的最小可实现集合，不是按输出引用得出的2项/1项。纯v2原语直接读 C02 的20份、D02的10份HTML；但直接删掉current metadata或companyfacts会破坏已使用的选源/年度身份检查。

## 选源完整性必须保留

1. 继续由原 annual adapter 验证配置主体政策和实际年度区间；cross-entity authorization仍为false，不能接前身proxy。
2. 完整current submissions经真实最后请求证明进入。完整recent列与files声明不裁剪；每个history的日期/CIK名称要合法。任何shard filingTo进入当前年度结束日之后，都必须保留既有 `RELEVANT_HISTORY_NOT_LOADED` 阻断，不能因最小化而忽略。
3. 在已证明的当前区间里，DEF14A/修订/年度原件都从同一current metadata自动选择。C02只用年度结束后同主体proxy；无当前proxy时才允许唯一同期间Part III修订。缺acceptance顺序、后续治理修订、需要多份语义合并时仍明确限制，不根据结果内容挑原件。
4. D02只形成ordinary原件披露；Southwest和Paramount的AMENDMENT_PROCESSING_REQUIRED/current_latest_verified=false仍必须保留。
5. 不再为了生成无关的C04限制而运行C04获取路径。全局原请求ledger保留真实历史，包括失败；不能把减少任务依赖误写成抹去失败记录。

源码路径：`normal_text_input_v2.prepare_normal_business_text_input` 目前调用整个 `prepare_saved_governance_input`；后者在已完成current/proxy选择后，继续读current/prior accession index、auditor XML、8-K全部primary/header并把其proofs塞入binding。`text_results_v2.prepare_business_text_sources` 只按明确text source_references取原字节，C02锚+治理、D02锚；它不访问8-K/index/auditor来源。故需要最小后继准备逻辑，而不能重写已冻结的V12函数或仅剪掉当前绑定内未被观察值引用的记录。

## R2/R3不可变凭据实证

已用现有 `verify_publication_bundle` 完整验证两份保存包：

- R2：`outputs/publications/publication_fe01e227848d6a4212318b4942742d06b0a2861df55e0b268df2062a441c438f/`
- R3：`outputs/publications/publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8/`

当前237个LEGACY中，205个（103个8-K正文、102个header）在R2 `internal/request_locator_provenance.json` + `release_input_plan.json` 中具有相同URL、accession、bytes SHA及**同一个request_attempt_id**。其已保存类型是 `IMMUTABLE_GIT_BLOB`，不是IMMUTABLE_ATTEMPT。逐一从receipt绑定的 `4d79b372f719aa45e0589d3d5b353d2b8f3b9848` Git commit重读body和header，验证size/SHA256/Git blob OID全部通过。它们均是C02/D02可退出的事件依赖。

未匹配的32项为proxy9、accession index8、auditor XML8、history7。R3 locator provenance只有本来已是IMMUTABLE_ATTEMPT的Marriott原年报，不能覆盖这32项。已有LIVE_SEC_ACQUISITION的93次请求也无同URL/accession/bytes的LEGACY匹配；进一步扫描现有完整请求ledger，同键的合格IMMUTABLE_ATTEMPT匹配为0。尤其必要的9份proxy，没有现成R2/R3不可变获取凭据可直接挪用。

这些结论不把当前LEGACY的类别改写为Git/attempt不可变类。若后续需要复用R2历史Git原件，必须引用原发布凭据和commit/body/header身份，保留原request attempt与当前最后请求检查；不能在HEAD现造一个Git绑定再冒充旧凭据。

## 最后失败请求反例

R2确实保存了Salesforce `0001108524-25-000083.hdr.sgml` 的较早成功Git原件：body SHA `bfa0eacfaf86153a213e4a9a0adfe31a30a941fe51e1aa952b7581057c69fb66`，request `request:attempt:ed0a791791ea5eb1d407e00aeb895701db82bc8902e9ec37cc66f4651c03f987`。

但当前ledger最后真实GET是第844行、`2026-07-09T08:56:16.899501+00:00`、status 0 / SSL EOF，attempt `request:attempt:7cd5ba82de3138295c0fcaa8499597bca7f3ca6b16bbc11ea723b261eaf5bf44`。历史Git原件不能解除该当前失败或充当新成功；本次205个匹配另逐个验证其当前最后GET均是对应同attempt成功。减少C02/D02依赖可以不使用这个无关URL，但不得用旧成功恢复C04。

## 审计文件

- `text_dependency_audit.json/.log`：292来源类别、逐坐标最小集、237个LEGACY逐项R2匹配、完整旧receipt locator和当前最后GET。
- `text_dependency_publication_verify.log`：R2、R3完整发布包验证。
- `text_dependency_immutable_attempt_search.json`：完整当前ledger同键IMMUTABLE_ATTEMPT搜索结果0。

最小后继建议：保留原公开API，内部使用原annual准备、同current原件的metadata parser/排序/真实 `_Sources.primary`，只组织4项或3项来源；正常输入binding仅绑定这些必要来源与完整选源证明。保留原LEGACY9及修订/失败语义，不增平台，不补造获取信用，旧冻结输入/Run仍按原字节解释。

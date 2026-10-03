# D03 来源锚点后继：限定差异独立审阅

**结论：未通过本轮限定独审。** 审阅对象为 `225842f06bcf73300917d643a4a51f5a8ff93958` 相对直接前驱 `8c26b6e273585e5a846cbdd551159f97d8f878f0` 中的 `regulatory_fact_review.py`、对应测试，以及 `run_fast_tests_v2.py` 末尾新增的一个 selector。新路径确实移除了向模型传递旧 `source_statement_facts` 判断和原验证器强制接受 `SOURCE_REPORTED_FACT / CURRENT_AS_REPORTED` 的机制；但它还不能可靠地表示每个锚点已被单独判断，也不能独立证明携带的来源引用和登记主体绑定。结论仅针对离线候选，不改变旧模块四次未通过的历史审阅，也不授 D03 真实调用、完整结果或生产信用。

## 发现

1. **P2：同一锚点上的相互冲突分类会清空未决标记。** `validate_candidate_response` 先要求某个 finding 引用锚点所在 `block_index`，随后只要匹配集合中**任意** finding 为 `CURRENT_REGULATORY_ACTION / ONGOING_AS_REPORTED / TARGET_REGISTRANT`，就不把该候选加入 `unresolved`（`regulatory_fact_review.py:93-115`）。用保存的 JPM 来源构造两份离线响应：仅 `OTHER_ENTITY` 时，`source_fact_candidate_review=1, unresolved=1`；同一块同时给 `CURRENT_REGULATORY_ACTION` 和 `OTHER_ENTITY` 时，两个 finding 都通过并保留，但 `source_fact_candidate_review=0, unresolved=0`（`conflict-probe.log`）。这与新提示要求保留冲突、异常主体和时态未决不一致。引用键只有块号，没有候选 ID 或句子范围；若一块产生多个候选，同一 finding 也可被复用为全部候选的“已评估”证据。建议把响应中的判断明确绑定至各 `candidate_id` 或原文句子范围，并在同候选出现互斥判断时保留未决；修后增加相应反例。

2. **P2，后续接线前的来源边界：来源引用和登记主体只从传入的旧 request 复制，未独立核验。** `candidate_request` 比较了块的字节位置、块摘要及句子包含关系（`regulatory_fact_review.py:43-58`），但 `source_reference_id`、`subject_binding` 与 `legacy_diagnostic_source_fact_id` 直接取自 `source_statement_facts`（`regulatory_fact_review.py:59-69`）；原 request 的 `request_id` 只是对其自身字段重新求摘要（`regulatory_fact_review.py:34-42`）。在保存的 JPM request 上仅改来源引用和主体绑定、重算 request_id，新的候选与响应校验均接受，见 `anchor-binding-probe.log`。这是**合成篡改输入**，不证明当前 `requests_from_source` 会生成错误绑定；它证明本模块不能单独充当来源真实性证明。接入真实来源链前，须从已绑定原件重建并精确比较旧 request，或逐项核对来源引用、主体绑定与已认证的 source/document 记录。

## 已确认与边界

- `candidate_request` 删除旧 `source_statement_facts`，保留原 `units` 和 `required_candidate_assessments`；新锚点不包含旧 `status`、`reported_time` 等强制答案字段。单个非当前分类（测试中的 `CONDITIONAL_OR_BOILERPLATE`、`OTHER_ENTITY`）可通过并增加未决。候选块若被放进 `context_only_source_indices` 或完全没有 finding，校验拒绝。上述冲突和多候选问题是这条保障尚不完整的具体边界。
- 差异没有改旧请求工厂、旧验证器、默认执行入口或调用权限；仓库中新增模块仅由新测试导入，`SOURCE_TESTS` 中 selector 恰好一次，`FAST_TESTS` 中没有。没有进行 provider/SEC 调用。
- 定向材料测试：`PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_regulatory_fact_review -v`，1 项通过，见 `short-test.log`。`git diff --check` 对受审三个文件通过。测试只覆盖保存的 JPM 单锚点与少数人工响应，不验证模型语义正确性、全部公司/原件、原生 Result/Run 或后续真实接线。

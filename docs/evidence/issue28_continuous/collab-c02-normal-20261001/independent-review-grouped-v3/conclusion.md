# C02 grouped v3 限定独立审阅（2026-10-01）

**结论：NEEDS_FIX（限定 API 契约）；普通更新链的分组与回读证据通过本次检查。**审阅对象是 `f4e4c4f62a1536b8bd265ced3ddf00962aaee9b6` 相对 `3a661897ed72a748f793209cadb124c0ba4bc8c3` 的指定路径。发现一个可复现的版本错配误接受：直接调用 C02 文本 API 时，v2 Spec 可以搭配 v3 的分组策略生成 `PUBLISHED/EXACT` Result，而 Evidence 不含分组的入选/上下文映射。现有普通 `prepare_case`、`replay_case` 将二者配对；本次**没有证明正常 Run 可以保存并冷读此错配**。因此该问题应按 API 边界修复，不能外推为 Macy's 私有 Run 已错误，也不能将本次机械检查提升为内容、390 坐标或生产信用。

## 可复现问题

`scripts/vnext/c02_composition_text_results.py` 第 24–26 行的 `_prepared` 只检查 `c02_selection_policy` 属于两个可选值，未核对 `compiled_spec['compiled']['disclosure_group']`。同文件第 78 行又只按 Spec 判断是否把原始块映射放进 Evidence。结果是策略与 Spec 交叉使用时，候选和 Evidence 分别按不同版本解释。

在当前保存来源上，调用 `prepare_case(ROOT, 'enphase_energy', 'C02', c02_composition=True)` 得到 v2 Spec，把返回的 `text_arguments['c02_selection_policy']` 临时改为 `COMPOSITION_GROUPED_V2` 后，依次调用 `create_deterministic_text_candidate`、`build_text_evidence`、`build_text_review_unit`、`create_system_review_decision`、`replay_text_result`。实际得到 **28 条分组观察、Evidence `PASS`、分组映射检查 0 条、Result `sha256:e5c26c106f59968e2803bcd4c00f704c19ec5f506d9e3a4f9a5af17ddd01c387` 为 `PUBLISHED/EXACT`**。这绕过了 v3 才引入的映射语义，但仍带 v2 Spec 身份。反向把 v3 Spec 配旧策略，当前在 Evidence 构造处抛 `KeyError: 'selected_source_blocks'`，未按版本错配给出受控拒绝。

建议在候选创建、Evidence 构造及结果重放共用的入口强制 `c02_composition_facts_v1 ↔ COMPOSITION_FACTS_V1`、`c02_composition_grouped_v2 ↔ COMPOSITION_GROUPED_V2`，并加两个交叉错配负例。不要靠普通 `prepare_case` 的当前调用约定代替 API 内的契约检查。若更改绑定文件，按实际受影响的 V13/V14 与收据重新验证。

## 已独立核对的正向边界

- 指定短测 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts python3 -m unittest tests.vnext.test_normal_c02_composition`：**9/9 通过**，53.446 秒。受测的 10 个产品文件 SHA-256 与 Git blob 均和 `f4e4c4f` 一致；`grouped-v3-commit-verification.json` 当时为未跟踪的事后记录，本审阅另用 `git show`/`git hash-object` 核对了字节。结论仅绑定该提交的指定产品文件。
- 分组源码先在完整原件上选块，再按相邻选块最多相隔两个上下文块分组；每个原块进入一个且仅一个分区。其每块原始 byte-span hash、分组 raw hash、完整分区和所选块顺序均在重放时检查。独立读取 Macy's 保存来源与私有 Run：原入选 **99** 块成为 **29** 个分组，29 条 Evidence 摘录均带 `selected_source_blocks`、`context_source_blocks`、原始块区间和完整分区 hash；独立核对这些分组的 raw span hash、分区覆盖及入选序列。原记录 `d7eaa03e...` 的另进程禁网候选冷读再次得到 `PUBLISHED/EXACT`。这证明机械映射和保存链，不证明 99 块的业务内容无误。
- `_derive_candidate` 对完整分组数超过 64 或可见文本超过 64,000 字符直接拒绝；指定测试将相邻阈值设为 0 时，Macy's 超 64 触发 `TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND`。没有看到取前 64 条的路径。
- 当前 V13/V14 Snapshot 可加载且 `validate_execution_authority` 通过，closure 分别为 `sha256:5be5192a08a37ddb45edc7f5c1a6c73949a055456ea412a8d64413e8c8611028`、`sha256:5e10a12f388d00cf8af4db539e2d5a139cfe279103f9e01017376d3a69e19d3b`；V14 `validate_semantic_rule_bindings` 与正式 wiring receipt 校验通过。三份重签收据的 `execution_authority_hash` 均为 `sha256:09241478fa9452ea16455a133f438337d2fa86bfe2b0cdc1537ac7ab786b3722`，但未把另两份收据当成各自完整业务入口已获授权。
- 默认 v1/v2 的路径及 v2 候选身份在指定短测中保持；另用旧安装目录的原代码与原 V13 Snapshot 独立重放旧 v2 Run，得到原 Result `sha256:8fb7d6e3ee0a8eeefd58b9187c701b11a3b1bb3aa4954dc339da4b704044f234`，旧 closure `sha256:b9207c3b86f9d4a244ad42342db9b6ffc88de81a3492f6d4111cc83f6730851b`，Run 仍 `OPEN`。没有以当前 Requirement 重新解释旧包。

## 未覆盖与权限边界

未重跑大套件、全部十家公司原生 Run、Macy's/其他公司 C02 的逐句内容判读、真实 SEC/provider 调用、正式 390 结果或生产采纳。对方 #47 工作树与 PR52 未操作。现有 Macy's 私有 Result 的 `PUBLISHED/EXACT` 是保存来源机械状态，不是董事会构成事实的内容验收。除本文件外，本审阅没有修改产品代码、原件、账本或执行状态。

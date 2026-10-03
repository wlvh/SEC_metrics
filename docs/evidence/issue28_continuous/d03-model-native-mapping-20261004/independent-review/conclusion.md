# D03 开发响应映射有限独立复核

结论：**PASS_LIMITED_DELTA**。在下述范围内未发现需要修改后才能交付的缺陷。结论只认可开发响应进入原生待审记录、重读绑定与拒绝边界；不认可 D03 语义、公司结果、DeepSeek 实际执行、正式采纳或生产权限。

## 确切对象与权限

- 检查提交：`ccb0c5e65cda6150b66bc07081ba0b7329bb152d`；比较基线：`be21d9f6164c6bbdb8c3ecad39bf4f81a5115732`。开始及结束 HEAD 都为检查提交，四项被审文件的工作树字节与该提交及父证据 binding-impact 一致。
- 产品范围仅为 `scripts/vnext/d03_model_processing.py`、`catalog/r6/D03_model_source_development_v1.md`、`tests/vnext/test_d03_model_processing.py`，以及 `tools/run_fast_tests_v2.py` 的一行 selector 追加。
- 读取了实际 AGENTS.md、相关架构/能力/行为/测试/PR 边界及 Issue #28 实时治理正文（服务器 updatedAt：2026-10-03T17:12:32Z）；读取 Issue 是治理元数据请求，不是 SEC/provider 业务调用。既有 README、构建与冷读记录只作为已执行证据和复核入口，未当作独审结论。
- 独审只向本目录写入结论和日志；没有修改产品、父证据、私有原包、#47/PR52 或其他工作树，没有 commit/push、provider/SEC/account 调用、长期测试或归档。开始已有 `execution-state.json` 修改，未覆盖。

## 独立执行与代码判断

1. 必需短测试独立执行：`PYTHONPATH=scripts /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_d03_model_processing`，7 项通过、0.129 秒。见 `unit-test-log.txt`。这些测试含合成来源，不能充当实际语义验收。
2. 在新进程禁止 socket 与 subprocess 后，直接调用读接口重新验证真实 Marriott 保存来源、六份 request/response、Spec、四记录、上下文和显示字节：4.243 秒通过；来源 SHA256 `5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b`、17 责任单元各一次，25 分类提议、18 未决完整保留。Candidate 与 ReviewUnit 分别精确为 `sha256:92dcda707632a0fbf661cd0704661e70ec5b8391bd6519fcb5cb55a3040b0cec`、`sha256:7d4d085ed67f317e6f2e78a11be1751fd1b60f1cfe4d5096942ebc4154e2e705`。见 `actual-cold-replay-log.json`。
3. 除仓库测试外实际执行 29 项有意义的边界探针（23.993 秒）：27 项拒绝、2 项受限正向控制。改模型/4096 输出预留/提示、缩短 native 请求的完整正文上下文、改原生单元身份或责任、漏 reviewed owner、跨请求原生引用、布尔或不存在索引、错 kind、仅上下文支持的 finding 和完全相同重复 finding 均拒绝。合法 owned native 加正文上下文引用保持可读；一个故意矛盾的合成语义提议及 Unicode 原值仍准确保存为 PENDING，说明此层确实没有暗中纠正或批准含义。见 `independent-boundary-probes-log.json`。
4. 私有真实包的临时副本独立注入原 request/response、review 显示/context、metadata、PENDING 状态以及外部 Candidate/ReviewUnit 身份篡改，都在预期边界拒绝。修改 response 后重签本地 metadata 与 DerivedAsset 也不能穿过外部原生身份和重建比较。原私有包逐文件摘要前后相同。真实 SYSTEM Review 入口拒绝该实际 pending 单元；未制造 HUMAN 决定。
5. 源码检查确认：来源由既有 ordinary_registered 组装器重新认证，再核完整 source 摘要；每个 wire 的外部摘要与完整源字节对应，native 共享表示恢复后逐单元相同，所有责任依原来源顺序完整且不重复。引用只能落在当前包实际拥有的 native 单元及完整正文上下文，且每个 finding 至少有本包责任引用。完整 model 原答进入 processing、Candidate 和 Review Context。
6. 实际记录状态是 Candidate `REVIEW_REQUIRED`、ReviewUnit `PENDING`；Evidence `PASS` 仅表示来源/请求/引用机械绑定，scope 仍为空、SYSTEM eligible=false。semantic_acceptance、company_result_created、native_result_created、native_run_created、provider_attempt_created 都为 false。程序没有生成 provider/WB-3/公司 Run/Result 或公开行信用。
7. 旧 ordinary default、调用控制、D03 原请求/内容验证器、Review 核心及旧政策在基线与检查提交间逐字节一致；V13/V14 authority 目录未变，也不含新 mapper/Spec。搜索产品调用处仅发现新模块自己和新增测试 selector，未改变正常路由。selector 确认只追加一行。见 `protected-paths-log.json`。

## 边界与剩余事项

此 helper 是显式开发接口，当前只允许单份 authenticated document；本次真实样本只有 Marriott FY2025。责任、位置、字节和原生 PENDING 的通过不证明 25 条提议是 25 项调查，也不证明当前涉案、主体、时间或缺失结论正确。故意矛盾输入保持 pending 是符合本层责任的行为，后续语义关口必须独立解决。

没有执行全 fast、完整 390、生产更新、真实 D03、DeepSeek 或独立人工语义验收；父会话此前测试并未算成本次独立执行。当前原件正负业务验证、真实请求工厂增加身份后的资源核对、获准真实用途、绑定/接线、实际 Review/Result/Run 和正式采纳仍为各自独立关口。本次没有通过记录映射替代这些责任，也未检验其他公司/修订多文档。

## 实际资源计数

开始 UTC `2026-10-03T18:12:11Z`，完成 UTC `2026-10-03T18:23:42.214346+00:00`，墙钟 11.52 分钟，未接近 90 分钟上限。保守工具计数 **50**（含最后核对：13 次 functions.exec 包装 + 37 次内嵌工具）；普通消息 **2**（初始说明、最终回复），无问题、无子代理。新业务调用 **0/0/0**。计数及最后状态见 `review-accounting-log.json`。

记忆只用来提醒验收层级不可互相升级（MEMORY.md:417–419、440–446）；本次事实全部按当前代码/提交和实际执行核验。

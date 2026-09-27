# D03 完整录制响应集合：一份来源，逐组原字节，独立冷读

当前保存来源把十家公司448单元分成130组，旧`d03_recorded_response_store.py`只保存一条带来源事实锚点的录制响应。新增`d03_recorded_response_set.py`仅补**离线**整组保存：先用当前完整来源和固定分组重建全部请求，要求每个原请求ID恰有一份字节响应，再按请求身份运行既有D03检查；JPMorgan带旧`source_statement_facts`的一组必须走显式`regulatory_fact_review`后继，其余组走原D03结构/引用检查。原响应逐组保存为`.bin`，来源只保存一次；封包索引记录原/后继请求ID、原响应SHA/长度、来源SHA与模块身份。冷读要求调用方提供**独立预期包ID**，重新认证保存来源、重建完整组序、逐文件核哈希并重跑检查。中断未封包、缺/多组、改原响应、额外文件和错预期ID均拒绝。

这是原始响应保存能力，**没有真实provider执行身份**。录制响应可以在结构检查中将候选标为背景，不能因为`unresolved`恰好为空就证明原文真的没有调查。封包固定`RECORDED_TEST_ONLY`、`calls=[0,0,0]`、`native_result_created=false`和`production_authorized=false`；无Result、Run、公开行或D03业务信用。真实调用仍待独立审阅与资源许可，原完整来源语义检查、跨组冲突、原生验收与公司结果尚未接通。原单响应模块及历史包字节不改，新模块不列入真实执行权限文件；`tools/run_fast_tests_v2.py`仅在source-material列表末尾追加本定向selector。

`targeted-tests.log`记录两项定向测试在本地用tokenizers0.22.2通过（117.372秒）：Marriott真实保存来源全部5组以含`U+037E`的录制字节往返、外部包ID/缺组/篡改/多文件反例；JPMorgan真实保存来源的带锚点组核对原请求与显式后继请求不同、审阅仍留未决。另用`record_and_read.py`在两个独立Python进程中，以Marriott同一实际保存来源创建外部私有包 `/private/tmp/issue28-d03-complete-recorded-20260927`，随后将`recorded.json`中的包ID作为外部预期传入禁网冷读；`cold-read.json`证明原5组和5组未决保持，调用`0/0/0`，原生结果仍为false。外部包仅在当前主机，不能声称仅凭Git材料即可在另一台机器读回。

测试里的回答是人工构造的录制值，特别是Marriott把必评引用列为背景，**不是对其原文业务含义的验收**。测试与独立进程均使用`original_sources_only()`阻止网络连接并禁止读取旧结果；没有复跑旧大材料、发模型/SEC请求或操作#47。下一步必须先保证模型回答的内容正确性和原生结果审查，不能直接把此封包接成结果。

精确补丁`065cbb87`的[限定独审](independent-review/conclusion.md)为`PASS_WITH_BOUNDS`：独立重跑Marriott五组短测与已有包冷读，确认旧单响应模块字节不变。审阅没有重跑JPM完整包；本封包只保存每组完整原始字节与**当前验证器**的发现/未决数量，不保存完整解释。将来若要进入原生结果，须同时绑定真实执行收据和完整解释，不能把相同计数当成同一业务判断。

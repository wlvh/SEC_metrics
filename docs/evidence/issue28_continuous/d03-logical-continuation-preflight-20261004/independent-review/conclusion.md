# 限定独立源码审阅：PASS

审阅补丁 `26ad04fbbc84f3316b927f349955e6a365d22c5c`，基线 `058c80b198cde14a05077c9e448048f895a117c8`，分支 `task/b06-new-source`。UTC 开始 2026-10-04 12:48:15 UTC；结束 2026-10-04 12:55:29 UTC。实际工具计数 **26**：10 次 `functions.exec` 包装调用和 16 次内部工具调用，低于 80 次上限；普通消息 2 条（开场及最终）。本审阅没有发现阻断这份离线原型交付的缺陷。

## 确切范围

只审此目录五个指定文件的新增离线 literal `continuedat` 链预检，以及已有 `scripts/vnext/d03_context_requests.py` 的 `_source` / `_xml_items` 和对应测试构造器。五文件工作区字节均等于精确补丁；两个既有依赖均与基线及补丁一致。读取保存的 source.json / all-started-chains.json 只核对原始来源表示和链身份，不读取、生成或审查任何模型回答；不重审旧语言分类或旧上下文试验。源和包的 SHA256 分别为 `5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b`、`cde003d55b88d4cd7f67a3a5d245fe03f034f88009c01c9f15c7cbfb7d3d0f4b`。

本次结论是独立上下文子代理的限定源码审阅，不是独立人工、指标语义批准或 DeepSeek 最终验收。未审本补丁另两份执行导航文件，也未审未来公司分组、调用接线或生产协议。

## 已核对的行为

- `logical_source.py:19–81` 在来源和单元字节认证后，以 `(document_id, element_id)` 查找；必须唯一命中本件文档的 `NATIVE_SUPPLEMENT`，原始类型为 continuation 且展开后的命名空间 URI 与 anchor 相同。缺失、歧义、错误类型/命名空间及循环均保留具体 UNRESOLVED 原因。多段失败仍保留已经解析的原始片段及未决目标；不把它标为完整。
- anchor 保留原 unit_id、fact ordinal、完整 wrapper、context、measurement unit 及各自命名空间依赖。直接对照原包确认全部 27 链的 72 个片段与来源中的 XML 或对应精确子串逐字一致，保留原 owner unit、root index、element id、相对位置及摘要；U+037E 未替换。输出深复制不能改动来源。
- `COMPLETE_XML_CHAIN` 只表示选定 anchor 的 XML 链走到终点。包始终保留所有原始 required_unit_ids，并明确 `full_original_scope_covered=false`、`semantic_acceptance=false`、`old_eight_location_contract_changed=false`、`live_task_authorized=false`。重新计算摘要后篡改任一范围/信用字段或将状态改成语义批准，重放仍拒绝。代码不产生 Candidate/Review/Result/Run，也没有生产代码差异可授予公司或真实执行信用。
- `measure_preflight.py:34–47` 的 `--check` 在重新测量之前返回；本次只对已保存的原源/27 链包执行一次短重放。其非 check 测量分支（56–99）只选择 ordinal 389、394、418、507，各自拥有 1、27、2、3 片段，共 33。五个已保存测量样本是四个单 anchor 和四 anchor 合包；不是原 17 单元/1229 事实的完整公司测量，也没有完整生产响应合同。原报告的 134632 合包 context tokens 包含 4096 输出预留；本次只核算记录算术及范围，没有重新调用 tokenizer 或证明 hosted usage。
- README 的 27/72、四 anchor/33、局部责任、原型位置及无语义/公司/旧八位置/真实调用信用说明与代码和保存包一致。它明确留下其他原始责任、重叠内容及最终分组；不能以局部 fit 推出完整公司请求上限。

## 有限验证及证据

两项指定命令退出码均为 0：4 个原测试通过（0.010 秒），一次真实保存包重放通过（0.409 秒）。另外补了 15 个有限断言：真实类型的两段原始 XML 正向对照、多段循环、后段缺失、后段错误命名空间、native-fact 类型错误目标、同 owner 重复 ordinal、未定义 anchor 前缀、数值 anchor 类型、fact/context/measurement-unit 的独立命名空间、输出复制，以及重新签摘要后的四项信用升级和状态改名反例。均通过；没有增加语义规则。

日志：`unit-tests.log`、`actual-source-replay.log`、`finite-controls.log`、`packet-identity-inspection.log`；精确文件摘要、执行命令、时间和工具数见 `scope.log`。

所有写入仅在本 independent-review 目录。未修改原源码、原数据、回答或账本；未 spawn、commit/push、打包或进行业务调用，新增调用 **0/0/0**。未访问或写入 #47 / PR52 现场；未执行旧长链、重新测量或赋予任何正式/生产信用。

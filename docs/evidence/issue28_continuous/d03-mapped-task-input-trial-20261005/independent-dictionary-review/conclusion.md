结论：REQUEST_CHANGES，发现 1 项 P2。实际 corrected-request 的字典修补、字节还原及旧材料可取回性通过本次限定检查；“namespace 缺失一律拒绝”仍有一条可达绕过路径。

审阅身份与范围

- 固定 head：ac25689cb8d5ae68512ebfb6fa09f677a645f95e；基线：4b910e8e927bdd9ccee10367c6828e99c30c30d6。开头与结束前均核对 HEAD，未漂移。
- 主审仅为 task_mapping.py 新增 _XMLDependencies、_complete_xml_dictionaries 及 prepare 的新增调用，新增 test_xml_dictionary_closure.py，以及 dictionary-correction.json、corrected-full-plan.json、old-compiler-preservation.json、old-compiler-exact-replay.log。
- 为核实可达前置条件与字节还原，有限读取既有 census/prepare、_source、_xml_items、_shared_units/_restore_units、测试 fixture 和保存报告路径。既有 14f74c3 的完整任务映射与逻辑链审阅继承未变范围，不重审业务语义或原模型答案；未读父参考。原 response.log 仅计算摘要并与基线 Git bytes 比较。
- UTC 开始：2026-10-04 16:44:23 UTC；UTC 结束：2026-10-04 16:52:24 UTC。最终工具计数保守为 32（functions.exec wrapper 及内层调用均计；含归档和最终核查），低于 80；2 条进度消息加 1 条最终消息，无问题、无 spawn。

[P2] 已在部分视图中的字典跳过 namespace 缺失检查

位置：docs/evidence/issue28_continuous/d03-logical-continuation-preflight-20261004/task_mapping.py:57–59（新增代码）。当 required context/unit 已在 present 中，代码只比较 definition，然后 continue；namespace_environment_id 的存在检查仅在添加 donor 的路径（66–68）执行。

有限反例通过实际 prepare 路径复现，而非仅调用私有 helper：同一文档、原生事实包含 c1，完整 XML supplement 明确引用 contextRef="c1"；c1 的 namespace_environment_id 为 context-only-env，但原 Native 字典只含 env。重新封存的 Source digest/unit IDs 满足当前 census 的实际准入，无 continuedat anchor，因此不触发旧逻辑链的 _xml_items 检查。prepare 仍成功，codec 重建后 shared_native_dictionaries 中仍不存在 context-only-env。只补回原 namespace 的正向对照同样成功，且 namespace 确实存在。输入满足现有前置条件并进入新增 present 分支；不是被更早拒绝的无效预检。

这使调用者收到一个引用已补足的任务包，但所引用 context 的 namespace 仍无法还原，不满足本次明确要求的 namespace 缺失拒绝。建议在所有 required 定义上检查原 donor Native 单元的 namespace 是否存在，再处理 present/新增分支；增加“已 present + 独立缺失 env”的拒绝回归。无需扩展语义规则或新框架。详见 finite-controls.log。

已通过的限定证据

- 指定 8 项 unittest 全部 PASS（0.033s）；覆盖完整嵌套 XML 的 contextRef/unitRef、相同重复定义、缺失/冲突/新增 donor namespace 缺失、精确共享还原，以及既有责任与逻辑链边界。现有新增 namespace 反例只走 donor 分支，因此未发现上项绕过。
- 仅从已保存 Source 重建 corrected-request 一份：精确得到 48adcf767a8d6f63208a79e4ad015f4653a30bc3bde3ae3d7125256a7da54c69，measurement 与报告完全相等，135342 context tokens，0.962s。未重跑 plan 或 16 份任务。
- 独立逐字匹配该请求完整 supplement XML 的 16 个不同 contextRef 和 4 个不同 unitRef，均在新字典中存在；定义及其 namespace 精确等于同文档原 Native 单元记录。
- 修后仅增加一个 dictionary_context_only 部分视图，原 parent_source_unit_id/document_id 精确对应原单元；只含 c-88/c-89，不含新 facts、unit_id 或原项责任。原所有 partial views 经 codec 还原后与修后前缀逐字节相等，整个还原 evidence_json_bytes 相等。Source/source ID、system 提示、request 设置、完整可见上下文、native context references/chain paths 和 69 个 owned references 与旧请求保持。
- 原请求 ca828c0551be54d246736f90bf325cc8133d5473adc286029913d858cb344496 实际可读取且摘要相符。原答 f5d5368d3c7c5f1e03f82a15c7fd8a03fe5cd214ba22d276d9071859aa38f9aa 实际可读取、等于保存摘要及基线 Git bytes。
- 保存 runtime root 的 task_mapping.py、mapping-prompt.txt、logical_source.py、replay_mapping.py 均等于记录摘要及 14f74c3 的实际 Git bytes。三项 scripts/vnext 依赖未复制在该 runtime root 中，但能从该 Git commit 实际取回，且当前依赖 bytes 与原版相等。旧编译器/依赖/原请求/原答均可取回；旧精确重建日志只读取，未重跑旧长链。
- corrected-full-plan.json 的 16 任务/3259 原项/149722 最大上下文以及全计划 refs 已解析属于保存报告；本次不将单份请求重建推广成新全计划独立验证，也不重新授予内容/公司/目标模型信用。

日志与边界

specified-tests.log、finite-controls.log、one-request-rebuild.log、preservation.log、tool-audit.log 保存本次实际结果。仅向本审阅目录写入 conclusion.md 和日志；源码、输入、旧回答、原账本未写。开始时已存在的 execution-state.json 修改保留。无 commit/push、业务调用、#47/PR52 访问或写入、tar；真实调用 0/0/0。此结论为同族子代理的限定增量工程独审，不是人工、DeepSeek、GitHub APPROVE、完整语义或生产许可。

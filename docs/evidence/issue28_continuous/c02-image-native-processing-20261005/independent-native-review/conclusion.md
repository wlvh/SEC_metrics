限定新增差异独审结论：PASS_LIMITED_NEW_CODE_DIFFERENCES

审核对象为 4459fcf9e402c0e3ae79708f2a0b104619e8c959 相对 ab56180588ded8b16728fa80e4d0d6dd2cec2331。本结论只覆盖 c02_image_context_c294b12f.py、c02_image_development_input.py、c02_image_model_processing.py、C02_model_image_development_v1.md、test_c02_image_model_processing.py，以及 run_fast_tests_v2.py 末尾新增 selector 和 TESTING.md 既有表格新增行。固定 Git 对象的差异、当前文件与该对象的字节一致性均已检查。未发现此限定新增代码范围内需要修复的 P1/P2 问题。

UTC 开始：2026-10-05 13:47:25 UTC。
UTC 结束：2026-10-05 13:54:57 UTC（证据检查结束及结论保存）。
工具调用合计：32，保守包含 10 次 functions.exec wrapper 与 22 次嵌套调用；exec_command 17、write_stdin 1、clock__curr_time 3、apply_patch 1，共 22 次嵌套调用。
普通消息合计：3（开工说明 1、进展说明 1、最终交接 1；最终交接在保存本文件后立即发送）。无问题消息、无子代理。未达到 80 工具 / 90 分钟 / 3 普通消息上限。

实际验证及证据：

- 指定三模块 unittest 命令实际运行于当前 4459fcf9 工作区，七份审核文件与固定对象逐字节相同。32 项全部通过，11.920 秒，exit 0；详见 targeted-tests.log。新图像模块 15 项、旧表格模块 12 项、可扩展性审计 5 项。
- 一次实际新进程、空 cwd 冷读完成，5.778 秒，exit 0。执行指定 check_read.py 的原保存源码；该脚本原本会重写已有 actual-read.json，因此仅在临时进程中将那一次报告写入重定向到本独审目录 cold-read-result.json。被测读取逻辑、原源码文件、原保存包和已有 actual-read.json 均未改。脚本禁用 socket/socket.create_connection/subprocess.Popen；启动执行器只创建本次测试和冷读进程。详见 cold-read.log、cold-read-result.json。
- 冷读由普通已保存来源入口重新选源和认证；normal_text_input_v2 实际重验 source_proofs、来源总账字节、主体和当前元数据范围，再重建完整文档、表格和新图像请求。新路径无 provider/SEC 发送、账本申领或账户动作。读取不是将父报告视作语义答案。
- 请求 SHA256 18abb36b70d36cb95052d564f7c3fd7e0373f46ccb612df934841c5926b48f6b；原答 SHA256 bf81745842cd3a53948b5c5bc44db1e9713d6e3193d34d0e4ad9ab22a540a3b2；原件 SHA256 bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476。原保存请求与接入包 request-body.json 完全相同；全部图像 markup 与接入包 sidecar 结构完全相同。50 项 facts、3 项 unresolved 均按原顺序和原内容保留于 processing 与 source-linked review context。604 个图像节点包含 7 个不在单元格内的节点。详见 identity-checks.json。
- 原生候选 d1298823a7fd72322d56596103fd8df23cb512d85a2003fe92aeceecc6a693db；完整来源/表格/图像 ReviewUnit b7d17001edbc72211e33d5aebeb94eeb3a00ebd8d9afc036e0f2b7aa10821aac（两者均为 sha256: 身份）。冷读用保存包外的这两个预期身份核对重新生成的对象。六份保存文件的 SHA256 全部与既有保存包相同，见 cold-read-result.json。
- 两份 ReviewUnit 实际保持 PENDING、normalized_scope 为空、system_approval_eligible=false；调用真实 _system_approved_claims 被拒绝。Evidence 的 PASS 只描述来源/请求及结构保存关系；MODEL_FACTS_REMAIN_UNVERIFIED 明确保留 semantic_acceptance=false。未创建 VerifiedObservation、Result、Run 或 provider attempt。
- 保存路径使用既有不可变字节写入，records.jsonl 最后写入；现有短测试实际验证中断时无最后记录、精确恢复、重复保存不改已有字节，以及篡改响应/表格/展示、错误外部身份、错误 origin、资源超限、源码/来源/账本/active 路径及符号链接拒绝。无新增保存故障可提升旧失败或生产信用。
- 另做短 Python -O 程序检查：多字节原文的原标签字节位置、表外节点、rowspan 单元格原点和布尔属性均保留；重复 img 属性与已改表格文本仍被显式 ValueError 拒绝。详见 optimized-context-guards.log；未增加模型回答。
- 八份旧 mapper / review / table formatter / builder / Spec / V13、V14 baseline 文件逐份比较 base Git 对象、head Git 对象、当前磁盘字节和登记 SHA256，全相同。固定差异没有 config/requirements 修改；普通 selector、旧默认返回类型和旧调用绑定不改。独审前后 git status 仅显示父任务既有 execution-state.json 修改及本独审输出目录；未修改源码、旧对象或原答。

代码审阅确认的新边界：

新请求在完整普通表格请求上显式增加 image_source_markup；全部解析属性和节点位置可逆恢复，原始标签拼写、引号和字节区间另存。_checked_input 比较真实重建请求的整个字节串，检验 tokenizer 上限与 payload 上限，旧纯块/表格请求和修改后的图像请求不能被换名接纳。源码重读重新认证来源并重建 actual wire、完整表格及全部图像 metadata，不从保存包的自签哈希单独取得信用。

完整文档/表格/图像输入与原生 context 仍在；事实和未决的引用分别可查到原文。图像 metadata 只提供原 HTML 声明，image_pixels_supplied=false，不把泛化文件名、alt、空单元格当成成员、资格或零。当前副本和保存身份说明程序如何处理这份实际输入，不能证明模型的选取无遗漏或业务赋义正确。

未覆盖并不得由本结论推导：像素解释、source-wide 遗漏方向或资格事实的独立语义正确性、全部公司/全部 C02 内容、DeepSeek 实际验收、新模型机会/费用/真实接线、正式 Review/Result/Run、Ready/合并/采纳/active 或生产批准。没有重新运行长测试、旧大演练或触及 #47/PR52/对方工作树。新增业务调用为 0/0/0；未读取或改动真实调用账本来申领任何机会。


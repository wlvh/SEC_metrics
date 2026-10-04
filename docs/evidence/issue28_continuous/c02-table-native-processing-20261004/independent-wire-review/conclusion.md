# 指定表格 wire 补丁限定独审结论

结论：PASS。在指定四个文件的新增接线范围内，未发现需修复的 P0/P1/P2 问题。该结论是独立代码与机械边界复核，不是 C02 内容方案成立、开发模型抽取、DeepSeek 验收、完整公司结果或生产采纳。

对象：`4c9e195e631f87e5c83f95c9eba46946d581ccde`，base `b8b11946fafce5363056511e4261a3950f7f4dfd`。工作区四个待审文件均与目标 SHA 完全相同；起始和结束工作区只见既存 execution-state.json 修改及本审阅目录。范围仅新 mapper、新 Spec、新测试及 fast runner 一个末尾 selector；提交中的其他文档/状态变更未作为本次代码复核对象。

## 实际覆盖

- 请求与原答绑定：mapper 先核外部两份原始字节 SHA，再从正常来源重建完整表格双消息请求，要求实际请求逐字节相等及资源计数通过；不调用旧 plain mapper 伪造请求。表格 grid、实际 wire、来源/原答/Spec/实现身份及来源分区都进入 native 审阅绑定。已审输入表示、来源/分组 helper、旧 mapper/view/Spec 与 base 字节相同，仅阅读与新增接缝有关部分，未重复旧长链。
- 完整性边界：全表格 grid 和完整 view 保存在 context/processing；引用与每项未决原样保存。逐事实原文、仅未决引用的 B1252/B1253/B1276 和所有表格文字坐标进入展示。完整来源分区证明机械覆盖，不被当作语义缺失结论。影像、样式及 raw-cell entity 表达限制保留；未推断空白格表示非成员。
- 信用边界：实际六记录是 grid DerivedAsset、processing DerivedAsset、Candidate、机械 Evidence、父/最终 ReviewUnit。两 unit 实际为 PENDING、SYSTEM 不可审批；分别调用 SYSTEM 函数均拒绝。Evidence 的 PASS 只核机械绑定；scope 未赋义。没有 Result、Run、provider attempt 或新业务调用。RECORDED_PROGRAM_TEST 的 model_answer_tested=False；补充测试亦确认 DEVELOPMENT_MODEL 仍 semantic_acceptance=False、PENDING。
- 保存与读取：相同字节复用且冲突拒绝，records.jsonl 最后写入。部分五文件包不能通过读取；同输入中断后精确续存可通过。自洽替换响应及重建整包仍被原外部 Candidate/Unit pin 拒绝。读取重新走正常来源准入、完整原文/表格构造及 request 比较，再与外部身份及全部保存 bytes 对比。相对/软链接/本代码根/其祖先后代/当前总账/active publication/来源输出重叠保护已检查；本审阅未访问或更改真实总账、peer 工作树或 active。
- 正常非空路径：35项定向 unittest 全部 PASS，0.239秒（进程0.357秒）。另做5项新的窄接缝检查，均 PASS：开发 origin 仍 pending、有效不同响应写入冲突、整包自洽换答拒绝旧 pin、部分包拒读、最终记录前中断精确恢复。补充检查用合成程序材料与临时目录，结束已清理；没有新增持久测试产物。

## 实际材料独立核验

只读 JPM DEF14A 2026-04-06 / accession 0000019617-26-000096。一次在 `/private/tmp` 工作目录禁 socket/网络及 subprocess 的正常源 native 冷读，5.447秒，未 mock 来源准入或 native 构造。所有六个保存文件前后 SHA 不变，全部 record/context/display 重现。实际请求 SHA `5397bcbfae90ffef4ead2f10ed27df8113d9250ea6f8f2668f17cb85951e9b1e`，原答 SHA `074c1b6b961e443c98168b8dccca8b978304e21da201515b97e613fb0d910d40`；来源 SHA `bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476`，原件2,932,247字节。请求530,507字节，129,805 input / 133,901 total reference tokens，409表。

独立直接读取已保存 SEC 原件，核七个实际引用的原字节跨度 SHA 与文字。实际 table_000116 是13行×21列，包含14个 image mark；这些图片内容未解释。B1253 单行原块把列标题连成一串，完整 table grid 则保留分开的列标题；该差异不被忽略，也没有以原块文字代替表格关系。两事实+一未决响应为已明确标识的程序对照，只用于正常非空接线。此处核验不形成独立模型答案。

## 未覆盖与停止边界

未重新执行已审51cc输入/来源长链、全 fast/CI、旧 plain 实际 mapper 长链、付费/SEC/provider 请求、账户操作、语义内容/完整缺失判断、真实抽取、更新/发布链或跨环境部署。未修改源码/测试/Spec/执行状态，未 commit/push/嵌套 spawn/打包。新 API 的任务文案与 origin 是调用者明确提供的开发元数据；没有把它们提升为受批准真实执行身份。

## 操作与时间登记

普通消息共3条：开头、一次进度、最终报告；问题0条。工具总量32（12个 wrapper +20个 nested exec_command，保守累计）；不超过80。首个调用确执行 `date -u`，但其聚合工具输出中段被截断且未保存该值，因此不捏造精确开始时间。可核的首份审阅日志 birth time 为2026-10-04T10:03:59.982447Z；静态读取开始早于该时刻，精确任务开始 UTC 应以父任务 RUNNING 登记为准。本次未触及90分钟上限。结束 UTC：2026-10-04T10:10:46.350731Z。

日志：targeted-tests.log、actual-cold-read.log、direct-source-spans.log、supplementary-boundaries.log、predecessor-integrity.log、scope-integrity.log、tool-accounting.log。原 check_actual.py 未执行，原证据文件/已保存处理包均未写入。

# 普通历史事件接收开发记录

本记录接续已有C01/E02–E05历史业务，仅在原历史分支开发，不新增PR依赖层，不扩已收口PR75/76。相同公司CLI消费已选发行人财年，读取/Item匹配/计算复用既有event_sources、project_event_result及Calculator，保存/读取/CSV复用公共实现。E01内容确认未接；继任主体必须批准的跨CIK事件窗口，在公共selected-source接口返回前具名IMPLEMENTATION_GAP，不能缩成单CIK窄窗口。

Marriott FY2024实际八个8-K/8-KA完整来源经过已有来源集合校验，五指标均0；同CLI首31.529s、禁止原factory复7.445s、独立读0.325s，45结果/pointer保持（精确文件数以cli.json为准）。0不是缺源默认值，旧独立阅读event-count-read-batch.json的marriott-2024也同时以申报日/报告日得到0，直接复用阅读，不重复原件全文。

正值测试Marriott FY2025暴露ORDINARY_PROJECTION_SELECTED_CLAIM_MISSING：适配没有在input_binding传实际claims，原失败保留；补传真实声明后C01/E03=3可保存和CSV读，含8-K/A，与既有独立阅读两日期基准同3。E02/E04/E05原0成功结果再次检查被公共_current_sources的重复legacy GET歧义阻塞；源getter_Sources.read同九份实际hdr以最终请求绑定均成功。不是源缺失、不删账本行，不另写历史controller；具体URL/attempt/原件SHA与最小复现是reentry-source-ambiguity.json，已直接交#28。

当前读口保C01/E03为REQUESTED_RESULT/CANDIDATE_READY、其余三个原0为PREVIOUS_RESULT/INPUT_OR_EXECUTION_FAILED，不冒充本次新结论。旧结果/pointer读取前后保持。完整正值同输入复跑尚未成立，不因零值回归成功而记整个事件族交付。

Macy FY2023的53周窗口2023-01-29→2024-02-03，E03=5 count，实际来源/计算/同一writer保存再读8.124s。与已提交独立阅读marriott之外的macys-2024（以报告末日命名）两日期基准/原Result ID完全相同；输出仍发行人FY2023，不改成公历2024或年化事件数。

20相关小例0.073s零skip：E01拒绝在选源前、继任主体不窄化、缺header/陈旧分片扣留而非0、未知程序异常外抛、catalog改为内容路线时明确拒绝。构造控制不当财报结论；真实零/正值/非自然年与小反例共同验证。原六个新consumer例还需公共runner按一方职责接收，不另建历史runner。

源码、保存输入与开发输出分离；新调用/费用/Run/接受0。公共复跑和多CIK接口、历史线上取源及完整约1950位置仍待。主要记录verification.json；材料恢复继续用原PR52已提交SEC导出，输入不依赖新GET。

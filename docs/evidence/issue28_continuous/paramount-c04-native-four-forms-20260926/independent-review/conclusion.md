# 46912cec 限定独立审阅：C04 四形式原生路线

受审提交为 46912cec61e981fc89750db27447710dba952aa2，直接前驱为 b4d21130d1945bd281dc88371adcd63daa900cdb。只审本次 C04 后继、普通 Run 接线、未冻结 V13/V14 绑定与指定保存日志；不重审旧 C04 或整个 PR。结论为 **NEEDS_FIX（一个 P2 错误接受路径）**。保存的 Paramount 正例本身没有被证明出错。

## P2：注册类事件可被历史分片日期索引静默漏掉，随后输出 0

旧读取器的 _filings() 只保留六种旧形式，不识别 8-K12B/8-K12B/A（normal_governance_input.py:27, 56-78）。其 history_body_alignment() 因而看不到只含注册类表单的索引与正文日期矛盾。新增 _registration_rows() 能恢复注册类行（c04_registration_successor.py:46-59），随后从所有已加载分片形成年度 events（102-104），但处理分片时又按当前索引声明的 filingFrom/filingTo 计算 needed_history，并跳过不重叠的分片（108-118）。没有检查每个 events 行都进入文件读取、来源集合及 Item 提取。各分片的 source_set_manifest 只核对其自身已选择的表单，不会发现整个分片被跳过。

隔离内存反例（无文件或网络写入）：设前期截至 2024-12-31、本期为 2025 年，某已加载历史分片的索引范围为 2024-01-01 至 2024-12-31，但正文含 2025-06-01 的 8-K12B。实际 helper 返回旧 _filings 行数 0、base_alignment_conflict=None；新 _registration_rows 发现该 accession，却计算 shard_in_needed_history=False，同时该分片满足旧读取器以前期截止日加载的条件。若同 CIK 当前/前期 AuditorName 相同，且其余已处理文件无 Item 4.01，新增判定在 c04_registration_successor.py:173-184 得到 matching 为空、comparison=False，接受 PASS/0。输入绑定甚至会列出遗漏的 event_accessions（245-249），而冷读重建同样的遗漏，无法纠正该数值。

应在排除历史分片前验证四形式正文行与索引日期范围一致，或至少断言每个年度 events accession 都被来源集合和已读取文件覆盖；矛盾必须限制 C04，不能给 0。增加一个注册类事件落在索引声明范围外、且审计师名称相同的反例，并检查默认两形式路径仍保持原行为。

## 可以认可的范围

- 指定短测以禁网方式通过 2/2：PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_c04_registration_successor -v。测试覆盖 Marriott 默认 v2 入口、显式 v3 入口及错误形式选择；默认代码路径在本补丁只增加可选参数与分支，没有改旧 resolver。
- 保存的 Paramount 运行根 /private/tmp/issue28-c04-four-form-20260926-02 仍可只读检查。其 summary 与提交的 summary.json 一致，manifest 的 run_id 相同；records.jsonl 含 22 条 Item 候选，分布于六个 accession，其中没有 Item 4.01；两份公开行字节哈希与 summary 一致。结果为 null，原因 C04_COMPARABLE_AUDITOR_FACTS_MISSING，公开行 WITHHELD；缺同 CIK 前期年报时没有给 0。native-repair.log 与 cold.log 报告新隔离根成功；第一次 native.log 的安装副本缺模块失败被保留，没有冒充成功。
- 当前加载的 V13/V14 Requirement 闭包分别为 sha256:85a83df9416014a489b2e3e8ed69df48a658688050e13af5b1e938e3c8c1b356 与 sha256:4defd18b3a3eae907ab59aec2065d65621666861dfb251d29ba3fe0d6592ae95。V14 执行权限哈希为 sha256:a7ba90e29c99106a1035d90ebcc9731fec98b494c3c7e8f34973ac3bc59c133d；只读 validate_execution_authority 与 validate_wiring_receipt 通过，SEC 收据所有证据哈希匹配。provider/SEC 指定日志是禁网模拟或录制测试，不是新业务调用；provider 收据仍明写 CURRENT_C04_DELTA_REVIEW_PENDING。

## 边界与统计

本审阅没有重跑真实保存来源的长原生链、安装副本冷读、两项约百秒接线测试，也没有做真实模型、SEC 请求、生产采纳、全 PR 或 #47/PR52 审核。正例与接线的执行结论以保存日志、现存运行根及当前只读校验为界；上述 P2 的前置条件通过直接调用当前两个 helper 的内存反例复现，未执行污染输入的完整原生 Run。工作区原有 execution-state.json 修改未碰；源代码、账本与其他目录未写。

实际工具调用：14 次顶层 functions.exec，内部 53 次 exec_command 与 1 次 apply_patch；无其他工具调用。只新增本 conclusion.md。

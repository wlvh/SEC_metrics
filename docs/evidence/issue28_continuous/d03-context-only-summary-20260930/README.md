# D03：仅上下文引用不制造公司级未决

实际触发是 `d03_complete_interpretation.validate_complete_interpretation()` 对完整录制回答做公司级汇总。V6 逐请求验证器会把 `context_only_source_indices` 展开成 `OTHER_MEANING` finding，并以 `UNRESOLVED` 填充与非行动陈述无关的主体、期间字段。旧汇总只看这两个字段，于是把明确作为背景处理的项误计为业务未决。

`reproduce.py` 使用 #28 已保存的 Marriott 完整来源构造五组**合成**的仅上下文回答，禁用网络。旧汇总条件会把第 0、1 组列为未决；修后不列入。修补仅排除能够在原始 provider 响应中逐项找到的 `context_only_source_indices` 所生成、且状态为 `NOT_AN_ACTION_STATEMENT` 的单引用背景 finding。模型显式返回的同类 finding 若没有这一来源、真正的 `UNRESOLVED` finding、行动主体或期间未知，以及 `unit.unresolved`，仍保持未决。没有修改 D03 提示、来源、请求、原答复或任何历史终态。

修后这组合成回答的分支是 `ABSENCE_RULE_NOT_APPROVED`：这**不是**“没有监管调查”的结论。程序并未验证模型把那些原文列为背景是否正确，provider 执行身份为 false，原生 Result/Run 也没有创建。`reproduction.json`记录真实保存来源ID、旧/新汇总分支及上述边界；定向完整入口正反测试见 `tests/vnext/test_d03_complete_interpretation.py`。新保存来源测试选择器只追加在 `tools/run_fast_tests_v2.py` 的材料列表末尾，测试运行器函数体不变。

本项不接 D03 真实调用；其独立资源与权限决定仍在。B13、D04及旧普通接口字节不因这项离线汇总修改而重签。原 #28 账本、#47/PR52和生产入口均未操作。

最终源码的两项定向测试通过；`fast.json`/`fast.exit`记录当前工作树142/142个快速selector通过（101.348秒），`source-selector.json`记录新增真实保存来源材料selector 1/1通过（22.768秒）。先前本机临时Python环境的`pyvenv.cfg`与tokenizers包元数据被清理，第一次重现因缺固定tokenizer未进入目标检查；已使用仓库锁定的`tokenizers==0.22.2`及wheel哈希恢复该**测试环境**。短命shell中的第一次`nohup ... &`仅留下空日志、没有测试进程与退出收据；改用持久执行会话后才取得上述`fast.exit=0`。测试失败/未启动与本项业务判断分开。

已推前一head`43d0445f`的主CI`36687688194`随后实际终态SUCCESS 16/16；它不覆盖本次尚未推送的D03源码差异。精确`2e687740`的[限定独立审阅](independent-review/conclusion.md)结论为`PASS_WITH_BOUNDS`：审阅者独立运行指定短测2/2通过，核对背景索引只能来自已验证原响应、显式其他含义和真正未决仍保留，并确认返回结构与零信用边界；fast及来源材料日志只读复用，没有重跑。新head远端CI仍待推送后核对。

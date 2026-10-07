# 六项旧 native/C04 CI 的有限离线诊断

固定源码：`01efa3d5d0fa486fac395ba4a3c931fc8dc1eb1b`。只读取、两次小型 Requirement 加载探针；未开发、未跑完整原件测试、未创建 Run、未安装 runtime、未发生真实模型/SEC请求。只新增本目录 `conclusion.md` 和 `diagnosis.log`。父方未提交的 C04 工作流替换保持原样。

Issue #28 实时只读取得 `updated_at=2026-10-07T19:13:21Z`，其受信任内部工具决定与提供的 `/private/tmp/issue28-closeout-active-body.txt` 一致。以下按当前保存来源收口范围判断，不把旧 AGENTS 防伪要求带回新路径。

## 直接结论

六个作业合计运行20项测试，16个错误全部在 **`normal_source_authority.py` 与旧祖先登记字节不同** 处停止；没有一个错误证明其后业务断言已失败或已经成立。4项通过也不证明完整六条运行链。两个日志均出现同一原因，不能合并成两批新增业务失败。

这个比较属于已退出新路径的旧源码封存/祖先证明要求。具体比较发生在 `requirement_profile_v12.py:90–96`，对应 **Requirement `issue_28_v11`**，不能因文件名 v12 就写成 Requirement v12。其后父链是 `issue_28_v13 → v12 → v11`，连续调用的 `issue_28_v14 → v13 → v12 → v11`；日常旧配置加载因此被无关祖先守卫先挡住。

小探针复现 v13/v14 各约1.11秒，同一 `RequirementError`。祖先登记期望 SHA256 `657eaec5…38be3e`、3769字节；当前源码 SHA256 `727197a9…f72988`、3771字节。日志记录完整值。这说明拒绝条件的来源，不证明当前修改的业务正确性。无需为了这些测试重新冻结新 Requirement、重签旧绑定、修改旧 Run 或全局忽略哈希。

## 六项分别处理

行号均指 `/private/tmp/issue28-7944-failed.log`。完整提取和第二份原日志对照在 `diagnosis.log`。

| 旧作业 | 具体停止点 | 可退出新路径必过集合的要求 | 仍须保留的义务与信用边界 |
|---|---|---|---|
| acquisition session / C04 update recovery：6项、4 errors | 257/341/415/499：`recorded_sec_session()` 357，或 `c04_update_cycle._configuration()` 46先加载旧 Requirement | 每次离线 transport/恢复检查也必须递归重建旧全树；新保存来源候选必须生成旧 checkpoint/native Run | SEC transport 的单次GET/零重试、已消费计数与失败停止、正确公司依赖、成功URL不被另一失败URL污染、恢复不重采；采集与计算分开。旧完整测试中这些断言此次均未达到，不能报通过。当前65项保留计数/来源等实际边界，但不自动等于此 transport＋checkpoint＋A08 Run完整链 |
| C04 source-only install：9项、7 errors | 1340–1925，7项均在最初 `recorded_sec_session()` 停止 | 新处理必须安装整套冻结 processing/Requirement；无关旧规则漂移也拒绝来源处理；防伪批准/固定前驱证明 | C04同主体/同CIK、当前与可比前期、四种申报及事件完整性、冲突/缺前期不能变成“无变化”；旧来源/程序/成功不被覆盖；已采来源在恢复中不重复消费。父方的3模块替换是**来源和主体检查**，名称已准确；不是 native 安装、混合 B01/C04更新或在线捕获能力的替代证明 |
| native cold read / recorded source update：首步1项、1 error | 1243/1276/1308，`test_normal_run_v3_material` 42尚在 SETUP加载 v13 | 新任务复制祖先全树、机械防重签攻击、OPEN/freeze封存仪式 | B03依赖当前B01、数值/单位/期间/主体、非自然年、事件来源完整性、文本出处/待审状态、错文件/错坐标不得输出。**同作业后续 `test_ordinary_source_run_material` 没有运行**；不能写成它已通过或它有已复现业务错误 |
| saved D04 native Runs：2项、2 errors | 1955/1988/2038与2041/2075/2121，分别 `prepare_requests()`、直接 v14加载 | 每个保存响应必须重建 Requirement→Review→Run整套证明；防重签/升级历史记录测试对新路径的硬要求 | 特定活动≠主体持续经营；历史/当期、肯定/否定、条件风险与缓解分别保留；缺单元/截断/不确定不能推出“未披露”；原引用及记录模式如实显示。现有 `test_d04_native_assessment` 已在65项队列，保留真实语义反例。它不证明新的D04公司完整Run/模型验收；当前保存来源入口仍明确不接D04 |
| remaining Marriott：1项、1 error | 1054/1087/1090/1093/1125，`build()`首个B06安装在 `normal.install_normal_inputs()` 281阻断 | 为当前PR重建该六项的旧 native安装和Run全链；强制SYSTEM审阅证明 | B06非正权益保护及账面债务范围、C03范围/人员/计量、C04比较与事件完整性、C02/D01/D02原文与来源范围不能被删。当前保存入口**六项均未接入**；不能用Marriott普通收入/酒店成功表示这些六项业务完成或改进 |
| remaining JPM：1项、1 error | 957/990/993/996/1028，`build()`首个A03安装被同门禁阻断 | 每次新PR重建六项旧 native全链和重签攻击 | A03/A04/A09/A11/A12/A13各自银行/业务范围、期间、单位与公式；A03原来源数值错误仍必须能被业务核对发现，不因攻击测试退休而删检查。当前保存入口**六项均未接入**；不能借普通JPM A08或D01旧读取替代这六项接受 |

“攻击测试退休”与“检查一个错误能否造成错误输出”有重叠，不能只按函数名里的 `forged/resigned/attack` 批量删除。例如错期间、遗漏事件来源、错误LCR输入、把不完整D04回答当缺席、恢复后重复消费仍是普通程序失误反例。可取消它们对重新签署、独立信任树和完整递归证明的依赖，保留业务断言或复用其已有效的原证据。

## 最小可执行处置

1. **只调整当前工作流的执行范围，不修改旧 Run/Requirement。** 对上述六个旧 native创建作业逐作业登记“退出本候选必过集合：旧完整创建/安装只在保存版本入口诊断”，不要标 PASS、skip或吞异常。检查名若继续保留，step/说明写清真正覆盖的当前来源、业务或旧读取范围；required-check规则保持原权限。旧测试源码和原runner保留。取消对新保存来源候选执行这些完整创建作业，不等于关闭旧读取能力、删业务或交付39项。
2. **复用父方已经实际通过的当前接缝。** 136当前公司集成、47恢复/混合、65来源/计数/请求与D04范围、8路由小状态，以及实际Salesforce混合、Paramount扣留/子集读取、Marriott C01未变复用，可沿其已测差异复用，不重新跑完整公司。六项旧job与这些当前证据不能一对一声称“同链替代通过”：尤其C04/D04/剩余12项没有进入 `CURRENT_METRICS`。新增工作流是否整体通过以该提交实际远端终态另验。
3. **保留当前C04来源检查及已有来源材料业务层。** 父方已有替换的可执行命令是：

   ```sh
   PYTHONPATH=scripts python3 tests/required_unittests.py \
     tests.vnext.test_governance_signals.AuditorSignalsTest \
     tests.vnext.test_c04_registration_successor \
     tests.vnext.test_normal_governance_input
   ```

   这保留C04原件/主体/期间/完整事件的有限义务。继承业务材料仍由 `python3 tools/run_foundation_ci.py --suite source-material --jobs 2` 按现有选择器执行；不要删其银行范围、整表、期间和文本业务测试来消除native作业。该runner采用 `inherited.FAST_TESTS` 分层，不会自动执行v2额外追加的C04安装material选择器；不需要为本诊断重跑或改旧v2runner。
4. **旧保存运行使用原保存版本，不由当前源码重新创建它。** 当前 `tools/vnext_company.py results` 依据公司任务布局分流；旧native状态明确需要原 `--runtime-root`、`--trust-root`。`company_result_read.py:12–23`将原runtime导入，再按旧manifest所指Requirement读取；当前来源候选则使用 `--source-root`，新读取使用其 `--output-root`。没有必要放松旧runtime校验。父方 `closeout-old-native-view-fixed.log` 已实际证明JPM D01旧任务通过这一当前CLI读取，0.636578秒、旧manifest/records字节保留；本诊断只读日志复用，不重跑。它证明这个被改动的旧读取接缝，不能泛化为所有旧Run或默认在线安装成功。

旧默认 `prepare_program()`/`install_runtime()`仍加载current-root祖先，不能因为接口保留就声称现在能完成新在线安装。`old-native-install-boundary.json`保存的早期失败也保留其原SHA/原原因。当前收口已明确仅保存来源候选，不必为此新增在线系统；报告这一边界即可。如果交付描述仍承诺“当前默认新安装/更新C04、D04或这12项成立”，就必须先删去该过度声明，或者另行获得范围并实际实现、验证；不能只改测试名。

## 未覆盖

没有重放六条旧完整创建链，没有新增C04/D04/银行/治理/text家族接入，没有验证新模型语义或新在线来源获取，没有验证全部旧Run。这里给出的PASS仅是**有限诊断/失败原因已定位**，不是六作业PASS或候选整体CI通过。未处理的普通业务缺口继续保留，不因退休工程证明而变成不适用、成功或已接受。


父会话结束登记（按本机代理session记录核对）：2026-10-07T19:29:45..19:36:28，约7分钟；20次exec工具调用、3条普通消息（2条进度＋1条最终）。没有继续调用该代理。此登记不扩大上述诊断信用。

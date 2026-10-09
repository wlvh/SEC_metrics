# 15260ba5 C04 原请求别名与财年标签限定独立审阅

**结论：PASS_WITH_BOUNDS；未发现本补丁范围内可复现的新增阻断缺陷。** 可以承接这次显式 C04 后继的离线接线和私有 Run 证据。该结论不授予正式采纳、生产切换、完整 390 坐标验收或新 SEC／模型调用信用。

审阅对象是 `15260ba5fead08d6cdd0e6cc66c344b5aea06aa5`，父提交 `084ed60139d847b182631ff549820b078f930b15`。检查时 HEAD 正是目标提交；指定源码、测试、V13/V14 三份 manifest 和本目录证据相对该提交没有工作树差异；限定 diff 的 `git diff --check` 通过。已实时读取 Issue #28，审阅没有触碰 #47/PR52、父会话执行状态、源代码或调用账本。

## 关键核对

- `c04_registration_successor.py` 只在冻结解析器抛出确切 `C04_SAME_CIK_FILING_REQUIRED` 时进入别名后继；其他异常继续拒绝。后继在 `c04_verified_document_alias.py` 中重新验证原 GET 证明，逐项绑定原 URL、accession、保存文档名、请求尝试 ID 和响应 SHA；SEC URL 必须按预期 CIK/accession 构成，主体、期间与事实维度继续检查。返回的仍是原 `SourceReference`，其身份和 `0002.body` 标签没有改签。选择及输入绑定分别记录原引用 ID、原请求 ID、保存名和真实 URL 文件名。
- 财年标签调用已有 `normal_annual_input_v2`：其 `original_input` 必须与本次已准备的年度输入相等，起止日期必须相等。Salesforce 保存材料中的发行人 FY2026 标签进入目标期间；原 DEI FY2025、Company Facts 值、政策 SHA 和元数据冲突状态保留在本次选择及输入绑定。这里审的是既有政策的接线与留痕，未重新审定政策本身。
- V13/V14 将两个当前执行文件绑定到新字节，V14 父闭包和 transfer 同步；`verify_current.py` 在本机通过，给出 V13 `sha256:744b75370388dc52ce2203f36ea2ad1af8a8f4782ba96ed66f268734651e80f5`、V14 `sha256:cc90fc7b8f9ad0a589e09fab64fc3088f8c6b092cdb5d8698d378c74cd546dd3`、执行身份 `sha256:f3c2c60b84173b6c0117100f32fcec531d4be4fc5701d8550acf7ce2c88492b2`。脚本核对 provider、SEC、普通刷新三个收据及其证据摘要（95/50/50 条），并确认冻结 `governance_signals.py` 字节未变。

## 本次独立验证和反例

- 必需短测本机重跑：26 项、`OK`，见 `targeted-tests.log`。第一次封装命令因 zsh 的只读变量名 `status` 在测试完成后返回 1；改用 `test_exit` 原命令重跑后进程退出 0，日志为后一次完整结果。
- 必需当前绑定脚本本机重跑：`PASS_CURRENT_C04_ALIAS_LABEL_WIRING`，见 `verify_current.log`。
- 我额外用同一合成年度事实试了三种错误输入：错误公司、URL 与 accession 不一致、原请求尝试 ID 对不上证明，分别拒绝为 `C04_COMPANY_MISMATCH`、`C04_SAME_CIK_FILING_REQUIRED`、`C04_ALIAS_ORIGINAL_REQUEST_PROOF_MISMATCH`，见 `negative-probes.log`。将既有年度标签返回值中的原输入或期末日期分别改坏，都拒绝为 `C04_REGISTRATION_ANNUAL_LABEL_SOURCE_CHANGED`，见 `label-negative-probes.log`。同一合成审计师事实在冻结解析器与别名解析器的字段、值及状态一致，只有预期的来源引用 ID 不同；此一例不代表所有事实形态的等价证明。
- 已检查本目录的保存材料脚本和日志，未重跑较长链：Marriott 的旧 Result/selection/input-binding 三个 ID 不变；Paramount 仍 `WITHHELD/null`，Macy’s 仍 FY2025；Salesforce 私有 FY2026 C04 为 `PUBLISHED/0` 且冷读脚本记录原别名引用与公开行核验。同一来源再次触发复用原结果。旧 Southwest 包以其安装代码根冷读成功；用当前新代码根直接读取旧包被需求快照身份拒绝，这两件事不可混称。现有 390 索引里 Salesforce/C04 原已是 FY2026 数值 0，此补丁新增完整坐标数为 0。

## 边界

大材料的 Salesforce 原生运行、旧 Southwest 冷读与 390 映射结果来自本目录已保存日志，本审阅没有亲自重跑或独立读取其外部私有状态。别名重解析器复制了冻结年度事实路径的多个语义判断；本次合成差分和保存样例没有发现漂移，但不能替代所有布局的全面等价证明。既有财年政策实现、普通来源证明验证器和正式发布链不在本次只读审阅范围内。当前结论限于补丁的原请求证明、身份和标签接线，不将录制或私有 Run 计为生产采纳。

工具计数：本轮共 28 次具体嵌套工具调用（26 次 `exec_command`、1 次 `apply_patch`、预计 1 次写后核验；经 18 次 `functions.exec` 包装，含一次语法错误和一次 shell 封装错误）。普通消息：0 条进度／问题消息，最终报告 1 条。若写后核验未执行，应以最终报告中的实际计数为准。

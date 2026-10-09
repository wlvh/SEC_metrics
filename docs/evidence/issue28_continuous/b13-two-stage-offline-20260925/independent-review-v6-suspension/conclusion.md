# B13 V6 暂停原生成功信用：限定独立审阅

- 精确对象：`d41a5e9adf6165b1ab3fc20aae63e689fdb9e228`，父提交 `a96fbe21756dceca007e15c84bb3380251847517`。只审 B13 V6 暂停增量、现有原生入口、回读、绑定和收据；前两份 V6 语义审阅的 `NEEDS_FIX` 结论保持原义。
- 结论：**PASS_WITH_BOUNDS，限于“V6 不能取得当前原生成功信用”**。未发现本补丁范围内可通过受支持的真实／录制执行、直接原生接受、保存回放或登记回读取得 V6 成功信用的路径。此结论不修复此前的错误排除和误拦截，也不批准 V6 真实请求、B13 公司结果或生产采纳。

## 停止路径

`continuous_semantic_calls.py:712-718` 对 V6 判断在读取账本扫描证明和申领之前拒绝，真实与录制模式一致；普通 B13 原生入口原有的 V5/V6 双阶段拒绝仍在 `:682-694`，扫描入口 `:697-704` 只建立扫描记录，没有指标结果。直接调用两种判断接受构造器分别在 `capacity_two_stage.py:366-369`、`:458-461` 拒绝 V6。即使仅做离线语义诊断，`validate_interpretation()` 的 V6 分支在 `:729-735` 固定增加 `B13_ASSERTION_SCOPE_VALIDATION_SUSPENDED` 未决，共用原生记录构造器在 `capacity_native_assessment.py:36-38` 不接受含未决结果。

已保存判断响应在 `native_assessment_replay.py:129-170` 回读时必须经过 `_acceptor()`；该路由在 `:25-27` 拒绝 V6。登记输入先通过此回读，再在 `capacity_assessment_input.py:242-250` 对双阶段组调用已加拒绝的 `build_registered_interpretation_acceptance()`。因此旧 V6 录制的原终态或收据不能靠当前重读升级为有效来源输入。私有 `_build_acceptance()` 若由调用者伪造无未决 `checked` 可单独构造内存对象，但不经过上述真实执行、保存证明或登记路径；本审阅未把这种内部伪造当作成功信用。

V5 的执行与回读条件仍精确选择 `SCANNED_VERSION`，V4 的普通 B13 路由和 D04 路由不触发 V6 拒绝。当前绑定下原第 190 次 V4 请求和来源原字节只读回放通过，原接受收据 ID 未变，新 provider 调用为零（`read-only-190-current.log`）。`route-check.log` 另外核对了 V4 普通 B13、V5 回读与 D04 的入口选择，以及 V6 三个入口的拒绝；它是路由检查，不是 V5 或 D04 完整 Run。

## 独立运行与收据边界

- 指定三套短测 **32/32 通过**（`short-tests.log`）；当前提交的 V6 禁网录制扫描后停止材料测试 **1/1 通过**（`material-targeted-uv.log`，108.593 秒）。材料测试核对账本只计扫描 `[1,1,0]`、无第二阶段判断申领，并分别触发保存回放与登记接受拒绝。首次用系统 Python 运行该材料测试在进入目标逻辑前因缺少固定 `tokenizers==0.22.2` 失败，原日志保留为 `material-targeted.log`；随后用离线 `uv` 固定依赖重跑通过。
- V5 录制加回读的本轮完整定向测试在 **119 秒上限**终止，未产生通过或失败断言（`v5-recorded-current.log`），没有继续重跑。先前 V5 混合 Run、冷读日志及两份超过 120 秒的旧 V6 录制日志只读查阅，均不冒充当前 V5 完整回归或当前 V6 成功。
- `binding-check.log` 用当前 V14/V15 加载器验证四个改动执行文件的 SHA-256 与大小，并核对 provider 收据 **58** 项和 SEC 收据 **15** 项证据哈希，均匹配。当前闭包为 `sha256:9c02b4772e364f33b311c10b6282dca3a4083ad0aad528d1ad2a75ce33956a3e`，执行权限哈希为 `sha256:ecaa9a4d7a9986006154caba08e227b4a35160f4678f4f04d85982e82ed1d061`。provider 收据记录禁网工厂复验、V6 停止材料测试和 `[0,0,0]` 新真实调用；SEC 收据仅对未改 SEC 材料做旧证据字节复验，没有声称重跑本次 SEC HTTP 或获得生产信用。provider 收据的独审状态仍是 `V6_SUSPENSION_INCREMENT_REVIEW_PENDING`，待父会话按本结论登记。

`git diff --check` 通过。没有真实 provider／SEC 请求、commit、push、生产操作或 #47／PR52 操作；既有 `execution-state.json` 工作树修改未触碰。V6 的语义问题仍须由新合同和独立验证解决，本补丁的验收范围仅是暂停其成功信用。

# B06 债券的短期与长期栏分别保留身份

Macy's FY2024（期末 2025-02-01）的原件把 `7.60% Senior debentures due 2025`
同时列在短期和长期栏：当期金额分别为 600 万美元和零。全表名称唯一守卫因此拒绝
`BOND_LEASE_BOND_MEMBER_DUPLICATED`，虽然两行的期限与原生事实不同。
执行者直接读了完整债务、租赁分类/到期、公允价值及采购承诺附注；这是开发阅读。

`historical_bond_sections.py` 只修来源结构。每个期限栏仍要求名称唯一；原生
DebtCurrent 与 DebtInstrumentCarryingAmount 按期限、维度分别勾稽，并绑定精确行、
当期列、单位、主体和金额。零值不删除，不把两个期限的事实按名称或维度合并。
重复名称分支还核对完整展开网格：所有解码文字、两期金额、表头、跨度和坐标保持，
只排除局部/全申报解析器生成的表号及 HTML 实体拼写。原始网格/来源摘要另保留。
没有公司、CIK、申报、年份或金额条件；名称全局唯一时仍走原原生读法，证明字节不变。

实际原件的 1 个短期成员、20 个长期成员及 21 个原生记录逐项相符。
账面借款 2,779,000,000 与另列融资租赁 15,000,000 的组件合计 2,794,000,000；
租赁附注包含的非租赁子项没有重复加计。完整来源检查随后仍拒绝
`BOND_LEASE_STANDBY_CAPACITY_NATURE_UNPROVEN`：该年备用信用证/可用额度说明不同于
冻结语法，不能把解除名称误拦当全部融资范围已证明。B06 仍 NONE/WITHHELD、value=null；
没有新 Run、接受、业务模型或 SEC 调用。接受登记仍 909。

## 检查与来源

隔离 worktree 中 10 项构造关系用例及 8 项完整原件/原反例复用，共 18 项通过，
78.947 秒，见 `isolated-regression.log`。新材料类继承原全融资范围反例，只换 inspector，
涵盖额外借款、金额、融资租赁/非租赁和采购承诺性质，不复制业务答案来绕过守卫。
完整原 scope proof 在名称唯一的当前原件上逐字节相等。构造用例另验证两期限均非零、
零行、同栏重复、六种勾稽冲突、同金额错期限、XML 冲突、上下文/网格/跨度错误及
不同表号与实体拼写。初次两个测试 fixture 放置/维度错误保留在
`initial-fixture-failures.log`，修正后通过，没有放宽被测守卫。

原短期600万对应 DebtCurrent 与 ShortTermDebtTypeAxis；长期零对应
DebtInstrumentCarryingAmount 的同债券维度。主文 SHA `29bc388b…`，XML SHA `5f4fd477…`，
原件来自已恢复并认证的取得包；未编辑原件或 #28 绑定的原检查器。
历史 Requirement 新增本规则并重铸开发快照，58 rule / 496 authority，继承项全相同；
固定模型执行包和旧 Run/快照不改。新来源层调度权重 95 秒是本地实测乘 1.2 的初估，
尚不是 CI 计量，单项及作业上限不变。

在已运行 `tools/vnext_historical_sec.py restore` 的来源根执行：

```sh
python docs/evidence/issue47_history/b06-older-years/bond-sections/probe.py <restored-source-inputs> <new-output.json>
```

脚本走正常期间/来源校验并禁止网络；原冻结拒绝、新组件及全部21条原生对应关系、
完整后续拒绝和原件附注正文一起输出。它只复现机械来源关系，不能自动完成语义验收。

已实跑的完整报告保存在 `source-probe.json.gz`，未压缩 SHA、来源及关键边界在
`source-probe-summary.json`。原冻结拒绝变为正确的后续具名拒绝，质量/发布/空值不变。

另有历史完整级联 13 项通过（240.410秒）及 DEI 引用/分片9项通过（5.931秒）。
快速层首次182入口中181通过，快照模块达到30.036秒并被原30秒限时拒绝，
`fast-first-batch.json` 原终态保持 FAILED。该模块单独5項通过15.731秒，随后用同一
原运行器、同一30秒上限仅重跑这个入口，16.673秒 rc0。
`fast-verification-summary.json` 如实列出两次执行合计核完182入口，没有声称首批全通过。
没有增加时限、修改快照守卫或删除入口。

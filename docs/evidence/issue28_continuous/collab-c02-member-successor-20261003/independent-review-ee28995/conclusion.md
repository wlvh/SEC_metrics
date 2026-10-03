本次限定独审结论为 **NEEDS_FIX**：确认本增量新引入一项 P2 漏选；另确认一项继承的职责误选局限仍阻断选择器完整准入。未发现新增 P1。3436 的定向移除、3409 正例保留及普通路线版本接入检查成立，但不能因此批准整个成员句式修复或整份 C02。

受审提交 `ee289953812c197734b543bf5282fe1e44142931`，父提交 `978e28e9b9b1d7a43d5b2ba83687900a417be4e8`。范围仅为修复46及普通接入的新增差异；继承 `independent-review-df9feaf/conclusion.md` 已结案的审计师修复范围，不重审全 C02／全 PR。本审阅是另一执行上下文的同族模型子代理审阅，不是独立人工验收或 GitHub APPROVE。

**新增 P2：明确成员名单因姓氏长度被漏选。** 位置 `scripts/vnext/c02_board_composition_28_v4.py:789–790`，相关判断在同文件 `813–815`。新 `_members_are` 把“这里出现了一个完整姓名”交给原用于另一场景的 `_mentions_person`；后者要求无称谓姓名的末尾姓氏至少三个字母。这把姓名长度当成了成员关系的限制。亲跑合成原文 `The members of the Audit Committee are Jack Ma and John Wu.`：本模块 `name_list` 确认是可识别的姓名名单，旧 v3 全文选择器选中块0，新 v4 全文选择器没有候选，返回 `NO_SUPPORTED_STATEMENT_PATTERN`。把姓氏换成 Smith／Jones 后新旧都选中，说明原因是姓名判断而非委员会范围。批准合同 v5 第97／99行包括明确的委员身份和行内成员名单，并没有此姓氏限制；这是修复46带来的实际退步，不能归为原件披露不足。

进一步亲跑一个两块的微型来源：先述董事会有12人，再述上述委员名单。Spec v4／GROUPED_V3 保留原块 `[0,1]`；Spec v5／GROUPED_V4 仅保留 `[0]`，成员事实被遗漏，而机械 Evidence 仍为 PASS。这是小型 Candidate／Evidence 检查，没有创建原生 Run。修复应正确识别明确的成员姓名关系，同时保留职责排除；不宜仅加少数姓名特例。共享实现和本方接入没有偏离不使该漏选变得可接受。本项是否作用于当前 JPMorgan 原件／Result，尚未验证，不能把合成反例写成该真实结果已经遗漏这些人物。

**继承 P2 局限：职责句里的他人姓名被当成委员构成。** 位置同文件 `789–790`，在旧 v3 对应宽泛成员句式中已经存在。独立判断 `known-remaining-role.py/json` 的原句只说委员负责监督外部审计师 Mr. Smith，没有说明他是委员，也没有委员资格认定；按已有合同应排除。亲跑该句及独立变化 `The members of the Audit Committee are responsible for reviewing reports from Alice Smith, the external auditor.`，新旧全文选择器均独立选中原块0。新 helper 仅检查动词后存在某个人名，没有核对姓名实际承担的是委员还是被监督者。这项并非本次新引入，却仍阻断将当前选择器授予完整内容准入。没有证据这两条合成句出现在当前真实来源／Run；不把其假设影响混同于已经确认并移出的3436。

**成立的定向修复与接线范围：**

- 已先按现行 AGENTS.md 的 COLLAB-28-47-v1.1、#54短入口及实时 Issue #28（updatedAt `2026-10-02T16:22:45Z`）确定范围。只读固定 #47 `4fcb1ebad662f915c87a5de9ac9c5bb2814f85b6` Git 对象中的实现和缺陷登记，没有 fetch、进入或改动 #47 工作树／分支／账本／快照。未复制其结果或验收信用。
- 从保存 Run 的 SourceReference／RawBlob 回到 JPMorgan `0000019617-26-000096` 原代理文件，核对完整原件大小 2,932,247 字节及 SHA-256 `bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476`。3409／3436 原跨度哈希与实际原文相等。3409 明述四名非管理层委员、各委员独立、财务素养及财务专家；3436 分配管理层、PwC、内部审计及委员会的工作责任，其负面执业说明不是批准的成员或资格认定。判断基于原文与已有合同，不由提供方选择数量反推。
- 直接读取保存的旧 v3／新 v4 Candidate、Evidence 和 Result：选中原块从59变58，只少3436，无新增原块；3367、3436不在新选中块或附带背景块中，3409原文保留于新 value。新 Result 为 `sha256:bc85895a9c396f66da4d0f915003b0c3d779f47827c377ba0c4439cf0c189ec7`，32组／58原块。本次是保存包及原字节读取，没有重跑真实材料／原生创建／冷读。
- 新选择器对旧 v3 的程序差异仅为成员句式表达式、`_members_are` 及其分派；其余是版本说明。新 helper、相关两个表达式及三个必要判断依赖与提供方 `historical_board_composition_v3.py` 完全相同，未倒灌历史分支，未接后续card修复47。旧 v3、Spec v4、旧审计师包装器相对父提交逐字节未变。
- 新 Spec v5 只增加明确策略及版本说明，保留批准范围、TEXT_V1、64项／64000字符和可逆原块分组。创建、Evidence、重放入口均严格对应 Spec v5／`COMPOSITION_GROUPED_V4`。共享参数默认 False，True 必须同时具备 composition／grouped／auditor 依赖和 C02 指标；默认旧 Candidate／Evidence 的字节兼容及错配拒绝由亲跑短测覆盖。显式 False 与真实材料准备相等的检查只读取执行方材料测试记录，没有冒称亲跑。
- 正常 CLI 的 process 分支实际导入 `ordinary_c02_member_update_v4.run_company`；C02写入独立 `metrics/C02-composition-member-v4` 历史，其余指标调用既有包装器。配置、输入描述、准备、安装、创建和保存输入重放均传播 GROUPED_V4；D02暂停门保持。没有发现本方接入的独立新增 P1／P2。
- 独立核对22个受审源码／配置／测试／Requirement 文件与精确SHA相等。V13当前397个执行绑定文件、101个规则文件，V14当前501个执行文件、61个规则文件均与声明的Git字节／大小相符；安装副本的全部397个V13执行文件，以及V13／V14两组五文件快照也相同。不声称C02包实际执行或安装了全部501个V14运行文件。
- 独立重算修前／修后两组闭包、执行身份及父快照绑定，均与 before／after 对应。修后 V13=`sha256:1b2fe50b46574602c4a4422f80ab3306bd4a0ce40024c955b64654e58aa0104f`，V14=`sha256:3117ac9bf6311c70f0648c2501e47a7438e625aaa2771c5ca92507a92caeec2f`。三份接线收据只更新执行／闭包身份字段，没有扩大权限。等价JSON是未提交补充材料：pre-commit已测试字节与后来SHA相等，不意味着原执行发生在未来提交SHA上。

**亲跑与仅读的边界：**

亲跑一次指定短命令，7／7通过，unittest 0.042秒、进程exit0，开始UTC `2026-10-02T17:10:14.814984+00:00`：

```text
PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_c02_member_successor.C02MemberScopeFastTest tests.vnext.test_normal_c02_composition.C02CompositionFastTest
```

另亲跑上述4个微型全文选择器正反例及1个两块 Candidate／Evidence 对照。日志在 `micro-counterexamples.log`。没有重跑材料测试、全fast、native、冷读或长链。执行方材料3／3（45.436秒）、正常CLI创建151.686秒、安装异进程重读44.662秒、正确root重复48.337秒、fast149／149（104.384秒）均只读取脚本／记录／日志。首次重复保存了旧父root，另建不同v4历史而断言失败；原失败、错误夹具说明和报告保留。修后在正确root返回同Result／NO_SOURCE_CONTENT_CHANGE、不创建第二Run，不能掩盖首次失败，也不能把两次不同root当同一次重复验收。

未逐块验收全部58块或全原件漏选，未验证其他公司／历史年度／留出原件／完整旧Run兼容，未复核全PR、390或生产。两份旧3367错误Result仍为 WITHDRAWN、released为空，旧私有 `53f2aa84…` 保持内容错误／无信用；新 `bc85895a…` 未获整份内容、漏选或390信用。本结论不授Ready、合并、正式采纳、部署或active切换。

审阅脚本先错误猜测五文件快照含 `post_freeze_tips.json`，实际为 CONTRACT.md；在任何短测前修正。第一次独立语义哈希计算漏了 canonical JSON 末尾LF，导致审阅断言失败；按 `canonical.py:419` 修正，原错误哈希留在 `binding-canonical-framing-error.log`。两项均为审阅脚本错误，没有改实现、绑定或旧证据。

产物仅为本目录 conclusion.md 和日志；没有开发、commit／push、spawn、修改账本或新建工作树，没有tar。业务 provider／paid／SEC 新调用0／0／0。开始UTC `2026-10-02T17:07:03Z`；结束UTC `2026-10-02T17:29:38.236615+00:00`。最终实际工具51次（functions.exec 24次＋嵌套 exec_command 27次）；普通消息3条（1条开工＋1条进度＋1份最终报告），问题0。未触及80次／90分钟上限。

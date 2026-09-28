# Marriott B01：跨财年自动选源的录制演练

本项检验固定普通更新入口在**来源目录从旧财年变为新财年**时，能否自行刷新元数据、选择新年报、保留旧成功并生成新Run。隔离根为`/private/tmp/issue28-b01-crossyear-auto-20260928`；运行时禁网，使用#28已保存的Marriott FY2024/FY2025两份年报正文与当前申报清单原字节，没有真实provider、paid或SEC调用，也没有修改生产指针。

关键来源边界：#28原根没有在FY2025年报提交**之前**实际收到的旧申报清单响应。`run-auto.py`沿既有`c04-adjacent-year-rehearsal-20260927/rehearse.py`的有限构造方法，从#28真实保存清单移除2026-02-10及之后的recent行，形成**构造的旧时点录制响应**（SHA-256 `5b542458aa0fa1c759eb2ff6d40b9f03520521103253ebbfaab7c5c132a2b8aa`）；它从未被SEC真实返回，不获得旧时点真实来源信用。第二步送入的当前清单是#28保存的真实响应原字节（SHA-256 `e3eeefe33c9c7351788d22a96ca36d061230cd2dacadbf44ed6ef79035742bd8`）。`reconcile.py`核对录制第1、2槽的正文分别与这两项字节哈希相等。

在旧录制目录下，`refresh_and_process(metric_ids=['B01'], max_sec_requests=0)`从真实FY2024主年报自行构造Marriott B01私有`CANDIDATE_READY`：FY2024收入25,100,000,000 USD，Result ID `c51c10da...`。保留同一状态根及旧成功指针，随后只把录制传输入口的响应换为当前真实清单，调用**同一更新入口**且`max_sec_requests=1`。程序自行选择`https://data.sec.gov/submissions/CIK0001048286.json`，以一次录制SEC捕获发现FY2025年报，形成新`CANDIDATE_READY`：FY2025收入26,186,000,000 USD，Result ID `e279b28d...`。新意图指向旧成功尝试；两个Result ID与Run ID不同，旧成功包前后整树哈希相同。这里没有为第二步手工指定年报URL、FY标签或B01数值；**构造旧元数据本身是测试设置，不是常态运行能力证明**。

`cold-one.py`从两次Run各自安装的代码和来源副本，在两个独立进程中重新验收Result、需求闭包和公开行；`cold-2024.json`、`cold-2025.json`均为`PASS`，当时1280个私有历史文件前后SHA不变。当前输入再触发`max_sec_requests=0`后，B01返回`NO_SOURCE_CONTENT_CHANGE`、没有新候选、旧新成功包均不变、录制账本仍0/0/2。重复尝试产生新`latest_attempt`并保存自己的终态，但`successful_attempt`仍指向FY2025 Run，这是正确的版本状态。

前段手工捕获对照的`preflight-repeat-wrong-assertion.log`和退出1保留：该测试错误地要求整个`current.json`不变，从而误拒了正常的新`latest_attempt`；只读`preflight-repeat-reconciliation.json`证明成功指针保持、最新尝试确为`NO_SOURCE_CONTENT_CHANGE`。最终自动选路演练的`repeat-auto.py`按这一状态模型检查，退出0；没有为修正测试再重跑前段长链。

`reconciliation.json`把两期年报来源URL、实际期间、Result/Run身份、前驱、自动选择的申报清单URL、录制响应哈希、两次安装冷读和重复状态对账为`PASS_RECORDED_AUTO_METADATA_REFRESH_TWO_FISCAL_RUNS`。两个年度的**B01局部候选**成立；总体`source_refresh`仍为`REFRESH_INCOMPLETE`、`refresh_and_process`为`UPDATES_INCOMPLETE`，因为本轮上限只允许一次录制刷新，其它已知来源待办没有被一并完成。因此不称为十家公司或39指标的完整自动更新。缺少真实旧时点清单与实际后来新年报的在线时间序列，也不称为真实新财年在线更新。历史390索引、正式发布和旧入口状态不改；原#28账本仍143/143/52，本项新增真实调用0/0/0，#47/PR52未操作。

精确补丁`c0e95d3a`的[限定独立复核](independent-review/conclusion.md)为`PASS_WITH_BOUNDS`。审阅者只运行短对账并逐项读取录制SEC收据、两期安装包及来源字节，确认真实保存的Company Facts中两期USD收入事实与公开行一致；未重跑长时录制/冷读。完整私有运行根没有入库，异机不能仅靠本目录重做完整冷读；此项仍是有界离线录制证据，不扩大为真实在线或生产验收。

**两项自动来源刷新补验。** 上述`max_sec_requests=1`只刷新清单，Company Facts仍列为待刷新，故整体未完成。`run-auto-two.py`在另一个隔离根重建同一个构造旧时点对照，然后对新期使用`max_sec_requests=2`：控制器自行先选`submissions/CIK0001048286.json`、再选`companyfacts/CIK0001048286.json`。录制层的限定路由只根据控制器给出的URL换入#28已保存且核哈希的原始响应，仍调用原`SecAcquisitionSession.capture`完成计划、申领、写线报与来源登记；没有替代发现器、报告认证、输入准备或原生Run。两项当前响应的SHA分别为`e3eeefe3...`和`af2fea71...`。第二步实际返回`UPDATES_READY / REFRESH_CHECK_COMPLETED / B01 CANDIDATE_READY`，FY2024→FY2025两个Result ID仍分别为`c51c10da...`与`e279b28d...`；旧成功包不变，新意图指向旧成功。录制账本3次SEC（其中初始1次为构造旧清单），真实外发0。两版安装包独立冷读、当前输入重复触发及`reconciliation-two.json`通过；重复运行设置`max_sec_requests=0`时整体再次如实`UPDATES_INCOMPLETE`，但B01为`NO_SOURCE_CONTENT_CHANGE`且成功指针不变。

这项补验支持**单指标、已保存材料、两项录制刷新**的完整更新控制流；不能替代真实历史时间序列。特别是旧期录制根的Company Facts本来就来自新年报提交之后的保存响应，程序按旧年报期间选FY2024事实，不能据此说旧时点曾真实拥有那份Company Facts。当前两项来源响应虽与#28实际保存字节相同，本次也没有向SEC发请求。不能把`UPDATES_READY`扩展为全公司39指标、十家公司新财报在线更新或正式生产就绪。

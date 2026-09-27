# Marriott B01+C04：一次有限刷新完成两份录制来源

此前混合B01+C04的真实保存来源录制测试采用每轮一条SEC来源、外部递交前次报告的受限续接；这覆盖恢复与篡改拒绝，却没有单独证明资料齐全时正常入口可在**一次运行**自行走完两份来源。本脚本只补这个明确验收缺口，不修改生产代码、历史原件或共享默认。

`probe.py`在隔离的录制SEC会话中，按已有测试设定保留旧处理副本，并把仓库请求日志已登记的Marriott submissions与Company Facts原始响应放在HTTP边界重放。`refresh_and_process()`一次传入`['B01','C04']`和有限`max_sec_requests=2`；每次捕获仍走原请求工厂、来源发现、当前处理副本及两个原生更新控制器。网络、DNS和HTTP实际访问被拒绝。输出`run.log`和`result.json`显示：申报清单、Company Facts各捕获一次，无`resume_from`；来源`REFRESH_CHECK_COMPLETED`，整体`UPDATES_READY`，B01与C04均`CANDIDATE_READY`。另一个Python进程从两个独立指标的状态根和原生Run逐份冷读，得到B01 `PUBLISHED/26186000000`、C04 `PUBLISHED/0`，Result ID及公开行SHA记录在`result.json`。

该录制账本模拟两次SEC槽，真实#28 provider/paid/SEC账本新增`0/0/0`；测试根结束后清理，Git证据不带私有Run。此结论是**当前已保存来源的Marriott B01+C04、一轮最多两次来源获取条件下**的正常完成能力，不是历史旧期成功→新财年成功的真实在线更新，也不说明所有公司与指标都不需人工续接。单请求受限时的认证续接及错误报告篡改负例继续由既有材料测试覆盖，不把本正例替代它们。正式采纳、调度、active和旧生产入口退出仍未获准。

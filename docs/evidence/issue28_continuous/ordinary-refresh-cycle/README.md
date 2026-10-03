# 有限获取到普通更新的接线材料

新增`ordinary_refresh_cycle.py`与显式后继`tools/vnext_ordinary_refresh.py`，复用现有获取会话、同一累计总账、来源发现和逐指标更新控制器；旧normal_update工具及原continuous获取器均未修改。新入口没有后台调度、发布或active权限，LIVE仍要求当前自身字节绑定、自己的离线证据和原SEC门禁。

## 已验证的实际增量

原生recorded来源/更新材料506.032秒通过，见`current-lifecycle.log`。读取真实保存原件作为明确记录响应，禁用网络、DNS及HTTP，在一个独立测试账本里完成：

- 自动选择JPM/Pfizer清单、Company Facts与JPM新发现历史分片，共先产生6个recorded获取尝试。Pfizer旧年报不在本轮保存测试库内，明确记录503，不冒充成功来源。
- 复用这6个尝试，在新的当前运行根形成两家B01原生候选。JPM B01按原Spec为`N_A_STRUCTURAL / TRAIT_NOT_APPLICABLE`；Pfizer B01为`EXACT / 62579000000 USD / FY2025`。不能称两个收入数值计算。
- 重复取得相同元数据内容后，两家均`NO_SOURCE_CONTENT_CHANGE`，原成功引用不变。
- Pfizer清单503后成为`INPUT_FAILED`，原成功结果保留FY2025且`current_input_matches=false`；JPM继续完成。后续轮次不自动重抽失败URL。
- JPM本地原文读取故障使其本次输入失败；恢复原始字节后复用原成功候选，修复过程没有发新请求。

以上生命周期额外产生6个recorded SEC尝试，累计独立测试账本12个；真实provider/paid/SEC均0/0/0。旧失败、原响应及首次Run失败目录保持原字节。

另以已取得来源沿同一普通处理函数完成JPM A08数值更新：`EXACT / 0.9115807340506899405928145595 ratio / FY2025`，72.959秒，见`jpm-numeric.log`。它与Pfizer B01构成真实原件下的数值正例；JPM B01继续保留结构性结果本义。

## 输入变化与执行绑定

JPM完整真实清单有两版：仓库baseline的`9934fad8...`和已获取新版的`b84e49be...`。在同一测试账本用两个明确recorded响应连接这两版，`older-saved-metadata.json`、`newer-saved-metadata.json`均形成新候选且成功尝试不同；数值/结构性结果的业务含义没有因重新请求而改写。两次响应继续保留原字节，新增真实调用为0。

首轮154.192秒的Run失败并非来源缺失：当时普通**UNFROZEN V14草案**（目录`issue_28_v13`，不是旧V13 engine）仍绑定旧ledger字节，而安装器复制了当前新增停止分类的ledger。根代理保留旧五文件后更新该开发草案执行绑定；新根采用`e2f4ac3d...`，原failed Run不重签。见`first.log`、`native-root-cause.log`和`first-initial.json`。

元数据变化后的max0重复检查曾在218.026秒处被V15校验挡住：测试运行期间`capacity_assessment_input.py`发生增量，启动时的执行绑定已失配。前两步来源和候选仍保存，见`content-change-interrupted.log`。当前V15 `c4bfed2c...`稳定后，已用新协调器完成两项max0接续：JPM元数据变化后的原成功引用和JPM A08数值引用均`NO_SOURCE_CONTENT_CHANGE`，未重建来源或Run；源清单字节及测试累计14槽完全不变。84.053秒通过，见`final-reentry.log`与`final-reentry-summary.json`。

接续脚本最初直接使用macOS的`/tmp`别名，历史目录的路径检查在获取前拒绝；规范化为其实际路径后通过，原拒绝保留在`reentry-path-rejection.log`，不修改路径守卫。

## 误完成、计数和范围边界

五项短测试覆盖未绑定LIVE不进入原SEC门禁、获取源根不可改向、有限请求配置，以及两项实际误完成风险：旧来源仍可读不允许掩盖capture异常；共享累计账差额不全部算作本协调调用。自身数从原生返回收据求和；LIVE有无法归属的额外槽时显示UNKNOWN/null，不能记0。来源发现/获取报错的公司保持`REFRESH_INCOMPLETE`。见`boundaries-final.log`。

`--metric`限定计算与历史更新，来源发现仍复用既有39项完整依赖图，所有获取受单次请求上限约束。来源图未完成不能升级为完整刷新。普通更新控制器仍只接36项；B13/D03/D04明确为**更新入口尚未接线**，不是三个指标完全未实现或真实披露缺失。正常生产授权、真正新财年、全部39项更新、统一正式发布与旧入口退出仍未由本材料证明。

## 完整材料与待审接线

`material-index.json`与`material-objects.tar.xz`沿用仓库既有还原格式，保留同一测试账本的14个recorded尝试、原始请求/响应/收据、完整源输入、原失败运行根、当前成功/失败/恢复历史及元数据变化历史。与仓库已跟踪文件逐SHA/size相同的字节只保存确切`repository_path`引用，必要新增字节按唯一`objects/<sha256>`保存；原始嵌套execution-rules压缩包也没有改写。

该包5995个文件映射中5644个引用已核对仓库原字节，新增201个唯一对象，压缩后6,609,492字节。直接使用既有helper，在新进程实际恢复5995个文件后逐一与原完整材料比较，全部字节相同，见`deduplicated-restore-check.json`和`deduplicated-restore.log`；没有重跑业务或增加调用。

```bash
python3 docs/evidence/issue28_continuous/b13-native-assessment/restore_material.py --evidence docs/evidence/issue28_continuous/ordinary-refresh-cycle --repository /absolute/checkout --output /absolute/new/restored-material
```

首次完整tar的成员/解压检查记录仍保留在`recorded-acquisition-archive-check.json`与`update-history-archive-check.json`；两个大tar及所有原始目录留在本地，未重复提交整库原件与运行代码副本。

`wiring-draft.json`记录当前执行绑定下的技术接线证据、验证过的坐标及未完成范围，等待根任务的相应独立审阅。它没有放到新LIVE入口读取的`wiring.json`路径，不能单凭该草案视为真实路线已启用，也不改变原SEC门禁或最终生产确认。

# 待批准执行计划

计划对象ID：`sha256:6b6c9d2a552fe39392ecf1c72afb0b9b6fe36a61b1a1fd406106b115cc7f0339`。本文件解释机器计划，不自行授予任何权限。
计划生成于 `2026-09-09T13:53:36.274419+00:00`，对应PR #40。

| 对象 | 实际身份 |
|---|---|
| 政策 | `annual_candidate_adoption_v2` / `sha256:159044d6584ec288e25841e8e5a458d83ceb6d738a787178973390aee354540f` |
| Requirement | `issue_28_v7` / `sha256:83bd7bb783da24b500e31aa27f1e2ceac2767d2af5bd76dca347733b96b75671` |
| 受审head | `8ca50dd7342e5132e888abe58620c38a8cd994be` |
| 实现身份 | `sha256:8ec3e518edf05934a3d9586906ca1709db3fec4e46a6e26d08e3350347d7d74f` |
| 测试身份 | `sha256:0e0ec555f619549f3fdd1f1c3471fa02d7eec895c07cdabf1dd342463b19423b` |
| 完整包 | `publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59` |
| manifest文件SHA-256 | `ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec` |
| 来源快照对象ID | `sha256:7cbba0c09497b884b46cbc6be037680601a5fcb5e60a4adf5b6c50963c216829` |
| 原候选文件集合对象ID | `sha256:4af14ac84329cb4227c204fa9cd8204d87af3a337e7ca53500f2ebff7e94d797` |
| 原执行 | `sha256:e2e9361b656772608e760e1b46cc46945aa1bd7d62f3ee5c5c3b4829b59b5a9c` |
| 两项结果集合对象ID | `sha256:602c70831a372dbd976795fd8a0fc0d744d8439795d25b2471205dd587ffcd86` |
| 前驱 | `publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8` |
| 前驱manifest文件SHA-256 | `69678ca9af53f7ca95f5250fd9eb319a90a9465da094f103a92ae0ed8e826d5a` |
| 实际发布根 | `/Users/lyuhongwang/Developer/SEC_metrics` |

完整包位置：`/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/publication/outputs/publications/publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59`。原B01/B10 Run ID、完整前驱指针与全部规则
hash均在机器计划中。两项采纳与238项继承合计240坐标/327公开行，B03不选中。
对象内容ID与文件字节SHA的计算对象不同，不能互换。

## 当前停点

PR40为Draft待集中审核，未自动合并。新Requirement与采纳规则未正式激活，实际
生产grant未签发，实际R3未切换。此计划为首次同年度来源/执行版本的候选特定采纳，
不授予Reader普遍资格，不授权模型/SEC调用，也不是39指标迁移验收。

## 审核批准后按正常入口执行

先审核`approval-templates.json`的两份正文：Requirement transition与独立publication
decision。实际Owner将其作为本PR的真实未编辑评论发布后，才有对应URL。此处唯一
未发生的信息是这两个批准来源及其GitHub时间；没有预填批准ID或签名。

合并必须保持计划指定的PR/受审祖先关系及实施与tests内容；使用merge commit。
合并并安全同步main后，入口核对该PR的真实merge SHA、第二父head及代码内容。
源码/政策/测试改变、目标根、前驱或包身份变化都会拒绝，不能偷偷换计划基线。

以下为已填路径的步骤模板，**本轮未执行生产动作**：

```bash
# 这两个值由上述尚未发生的真实批准提供；不是模型密钥。
export ANNUAL_ACTIVATION_COMMENT_URL='<真实Requirement批准评论URL>'
export ANNUAL_PUBLICATION_COMMENT_URL='<真实publication批准评论URL>'

python3 tools/vnext_annual_publication.py activate --plan '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/pending-production-plan.json' --activation-url "$ANNUAL_ACTIVATION_COMMENT_URL" --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/activation.json'
python3 tools/vnext_annual_publication.py release --plan '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/pending-production-plan.json' --activation-url "$ANNUAL_ACTIVATION_COMMENT_URL" --owner-url "$ANNUAL_PUBLICATION_COMMENT_URL" --operation deploy --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/deploy.json'
python3 tools/vnext_annual_publication.py release --plan '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/pending-production-plan.json' --activation-url "$ANNUAL_ACTIVATION_COMMENT_URL" --owner-url "$ANNUAL_PUBLICATION_COMMENT_URL" --operation publish --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/publish.json'
python3 tools/vnext_annual_publication.py read --publication-root '/Users/lyuhongwang/Developer/SEC_metrics' --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/read-after-publish.json'
```

每一步重新核对适用规则、真实批准及当前状态。部署只持久化inactive完整包；只有
publish提交单一指针。统一读取返回完整矩阵、证据及两项原始来源，不能仅检查显示数值。
已有完全相同的包部署可验证后复用；操作输出文件不得覆盖原记录。

## 失败与有限恢复

计划范围固定为publish/rollback/restore各一次，recover只属于同一已预留操作。
不存在自动模型/SEC重试，也不会用原PR38剩余名额。

```bash
python3 tools/vnext_annual_publication.py release --plan '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/pending-production-plan.json' --activation-url "$ANNUAL_ACTIVATION_COMMENT_URL" --owner-url "$ANNUAL_PUBLICATION_COMMENT_URL" --operation recover --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/recover.json'
python3 tools/vnext_annual_publication.py release --plan '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/pending-production-plan.json' --activation-url "$ANNUAL_ACTIVATION_COMMENT_URL" --owner-url "$ANNUAL_PUBLICATION_COMMENT_URL" --operation rollback --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/rollback.json'
python3 tools/vnext_annual_publication.py release --plan '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/attempt-02/pending-production-plan.json' --activation-url "$ANNUAL_ACTIVATION_COMMENT_URL" --owner-url "$ANNUAL_PUBLICATION_COMMENT_URL" --operation restore --output-json '/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/production-execution/restore.json'
```

有pending intent时先按同一plan/action/permission绑定恢复：指针前中断撤销到旧版，
指针后中断完成已提交新版。没有pending intent且同笔native收据已完成，只确认完成。
预留后尚无intent、或软失败已补偿，则保留旧完整版，本次预留消费；NO_PENDING和
ALREADY_RESERVED都不等于发布成功。若以后决定再试，需要新的实际计划及Owner批准，
不需要再开发发布功能。任何CAS前驱变化、来源/包损坏或权限不符都停止相应写入。

本轮开发中曾发生一次语义扫描默认输出误写兼容副本，已精确恢复并归档；这不是
实际发布。后续准备和演练使用OS级保护，最终审核须同时查看该事件与恢复证据。

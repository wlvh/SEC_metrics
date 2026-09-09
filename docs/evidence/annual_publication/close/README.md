# PR39 最终实现补验

A 实施提交 `77dd7f3407d09bec3e5d19356f11028a9038326f` 在原交付提交之后只将 `tests.vnext.test_annual_publication`
接入 fast 白名单。GitHub 原日志证明该模块实际运行4项测试并通过；CI使用PR合并测试
提交，本地首次 prepare 与正向演练使用上面的干净实施提交。具体身份见 run-binding.json。

新根首次 prepare 实际进入来源批准核对、原生图重放、扫描、投影和完整封包，状态
PREPARED_ISOLATED_COMPLETE_PUBLICATION，不是缓存复用。完整验证、switch和
PublicationView矩阵/证据/两项原文读取成功。随后原有两项正向集成测试均通过，
零SKIP：软失败、指针前后中断、受限隔离恢复、回退/恢复、冷读与重复prepare/publish。

- 完整包：`publication_a88ea14b596f2831e0b872daf6a4a6e84f8f8313b3aa161257ba88168a2ff528`
- 完整包目录：`/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-publication-close/final-rehearsal-2/outputs/publications/publication_a88ea14b596f2831e0b872daf6a4a6e84f8f8313b3aa161257ba88168a2ff528`
- manifest文件字节SHA-256：`e2767d023c24874e3f993cda6970400b74bf649c4e2da91b1e7a15259e53eb80`
- 采纳对象内容ID：`sha256:10e90490973883cce4d6ade1367512e2dc5e79eb4b26216c9c2c7d4200a683e7`；它不是收据文件的字节SHA。
- 240坐标=2采纳+238继承，327公开行；B03完整保留但未选中。

run-binding.json由bind_a.py从实际Git对象、执行记录、完整日志、原候选、包内context/
meta/adoption、CI原日志交叉验证。追加本目录仅归档证据；实施到交付的diff另行核对，
不要求日志包含自身未来commit。

独立增量复核来源及亲自执行/材料读取/历史承接分界见independent-review-a.json。
原8项重绑反例沿用父交付记录：本次未修改对应validator或反例，只改变fast选择清单。
这不是再次全仓审核，也不是新增正式发布权限。

外部采证工具首次因gh的text=True字符串未编码就计算hash而失败，原记录及新根保留
在harness-attempt-1；未生成包，未改仓库实现。修正采证工具后在另一全新根成功。
两次必要GitHub评论读取照实记账；故障/冷读完全禁网。业务provider/paid/SEC=0/0/0，
PR38历史累计仍2/2/0。实际R3、原候选、原运行历史、stash和历史worktree未改变。

A仅在最终交付CI、独立复核及全部硬条件满足后允许merge commit。合并后还需
post_merge_read.py只读核验实际R3、原v1包和本轮包。正式采纳/生产权限属于后续B，
本次隔离成功不表示实际R3更新或未来材料泛化完成。

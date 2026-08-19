<!--
PR body 原则：

1. 只写本 PR 已经完成的事实，不写计划。
2. 文件清单必须来自：git diff --name-only <base>...HEAD。
3. 测试策略与测试证据记录方式以 TESTING.md 为准。
4. 用户可见变化对照 interact.md。
5. 架构变化对照 architecture.md。
6. 每轮 review / 修复都必须写入“Review / 修复记录”。
7. 文档治理必须就地修正漂移，不得在没有替代路由的情况下删除既有权威入口、SOP 导航或长期解释内容。
-->

## 1. 背景与目标

---

## 2. 实现方案

<!--
写核心思路和关键取舍。
不要复述所有代码。

若涉及 source / artifact provenance，必须说明：
- source-input closure；
- acceptance artifact closure；
- stale proof 如何失效；
- publication 或 postflight 失败如何 fail closed。
-->

---

### Issue #15 delivery / Cutover（适用时必填）

<!--
R2 继续提供 SU-00–SU-11、AC-01–AC-28 与详细契约；R3 只覆盖其明确列出的决定。
代码已实现、recorded 已通过、active 已提交和 full 已通过是四种不同结论。
缺任一 Done gate 时本 PR 必须 Draft，第一行写 Progress on #15，不得写 Closes #15。
-->

- base SHA / head SHA / tree shape：
- immutable R2 hash / R3 Addendum hash / effective D-01 ID+hash：
- SU-00–SU-11 矩阵：
- AC-01–AC-28 矩阵：
- R3-D1–R3-D7 落地位置：
- recorded acceptance receipt：
- second layout accession/source/hash/receipt：
- post-freeze holdout accession/source/hash/receipt：
- second-layout-before-freeze / pre-holdout exact inventory / production semantic freeze proof：
- SEC Stage00/01/02/03/05 acquisition commands / ledger tail / inventory receipt / `formal_receipts.sec_acquisition` binding：
- release source plan latest verified immutable request-attempt binding / live legacy-locator rejection：
- live attempts/model/request/assistant-output/provider-envelope/observation hashes + portable audit closure：
- HUMAN decision binding：
- ten-company parity / migrated field diff / non-migrated diff：
- B03 reconciliation receipt：
- old producer/invariant migration + old-resolver-throws receipt：
- 14项 fault-injection receipts / verified legacy A→formal B→receipts→private official CAS proof：
- active publication / previous publication / root mirror hashes：
- Cutover / rollback / restore receipts：
- public generic formal receipt/commit fail-closed proof / three same-pinned-view terminal cycles：
- full acceptance / final snapshot hash：
- exact commands / interpreters / return codes / durations / stdout+stderr digests：
- GitHub checks present/absent（本地结果不得写成CI PASS）：
- 未完成与精确 blocker：

当前 evidence level（recorded / staging / active / full）：

-

---

## 3. 变更范围

<!--
必须来自：
git diff --name-only <base>...HEAD

只列本 PR 实际改动的文件或目录。
不要写当前 patch 中不存在的文件。
删除、历史化、重命名和新增导航文件必须单独列明。
-->

| 文件 / 目录 | 变更类型 | 说明 |
|---|---|---|
|  | 新增 / 修改 / 删除 / 重命名 |  |

---

## 4. 文档影响

<!--
只写受影响的文档。
如果没有文档需要更新，写：无。

如果本 PR 改变能力边界，请检查 capability_contract.json / interact.md / docs/business_user_guide.md。

如果本 PR 改变用户可观察行为，请检查 interact.md，并判断 docs/business_user_guide.md 是否需要同步。

如果本 PR 改变业务人员能问什么、怎么问、结果怎么看、什么时候该找人，请检查 docs/business_user_guide.md。

如果新增“能做 / 不能做 / 必须追问 / 必须拒绝”的声明，请确认它有 capability_contract.json anchor_id、真实测试锚点与受控 test_status；标签和 symbol 存在不等于 statement 已被证明。

如果修改 AGENTS.md、SOP.md、README_RUN.md 或长期总览文档：
- 保留既有一级导航和稳定章节编号，除非 PR 明确证明迁移必要；
- 不得把“减少重复”变成删除发现路径；
- 旧内容漂移时优先在原文件就地纠偏，历史化或拆分必须说明替代入口、兼容路径和迁移理由。
-->

受影响文档：

- 无

说明：

-

---

## 5. 用户与架构影响

用户可见变化：

- Yes / No
- 说明：

架构变化：

- Yes / No
- 说明：

Source / artifact provenance 变化：

- Yes / No
- source-input closure：
- artifact closure：
- stale-proof invalidation / fail-closed 行为：

文档导航变化：

- Yes / No
- 原入口是否保留：
- 新旧路径如何兼容：

---

## 6. Review / 修复记录

<!--
单 commit 策略下，这里就是修复历史。
每次 review、修复、merge-readiness 反馈后都必须更新。
重复问题必须记录：较早声明为何不足、本轮固定的不变量、反例矩阵与可原样执行命令。
-->

| 轮次 | 来源 | 问题摘要 | 判断 | 处理结果 | 证据 |
|---|---|---|---|---|---|
| R0 | 初始提交 | N/A | N/A | 初始实现 |  |
| R1 | Codex / Claude / 人工 |  | 真实存在 / 不成立 / 可暂缓 | Fixed / Won't fix / N/A |  |

---

## 7. 测试证据

<!--
每条证据写可原样执行的命令、实际结果和产物或日志路径。
不能用 quick unittest 代替 Golden、repair gate、snapshot checker 或完整场景。
未运行项必须说明原因、影响和对应 caveat，不得写成 PASS。

涉及完整性不变量时，至少覆盖适用的负例：
- dirty / staged / untracked source；
- 缺失、重复或多余 artifact key；
- SHA-256 / size 篡改；
- stale sidecar；
- symlink / alias；
- 构造/append 后直接修改磁盘并从 finalizer/freeze/replay 重读；
- transport policy 与实际 host/region/timeout/retry/payload/failure 事实不一致；
- untrusted input 的 span/table/text/expanded-cell/rendered-byte 资源上限；
- report 或 manifest publication failure；
- light package 缩小声明 source closure。

若改动 source-input closure 或 policy-bound 生成 artifact，必须记录：
- 冻结后的 source tree 在 clean 隔离 checkout 上 Stage 12 exit 0；
- terminal artifact diff 以独立 artifact commit 发布，或按单 commit 政策经
  amend 折叠进最终 commit；
- 最终 PR HEAD 的 source tree 与受测 source tree 等价，且 snapshot checker exit 0。
历史D-01 pending record不得误写成effective decision仍pending；缺SEC/OpenAI secret、HUMAN或live证据必须明确BLOCKED/NOT_RUN，不能伪造full PASS，也不能掩盖本可执行离线gate的真实失败。
-->

| 层级 / 目的 | 原样命令 | 实际结果 | 证据路径 |
|---|---|---|---|
|  |  |  |  |

未运行项与原因：

- 无

---

## 8. 已知限制与回滚

已知限制：

-

active / latest 区别：

-

OpenAI 处理器与 SEC evidence source 边界：

-

root mirrors 组原子性边界：

-

回滚方式：

-

<!-- rollback 只切回 committed predecessor 并重建 mirrors，不得重新启用旧 parser。 -->

---

## 9. 最终自检

- [ ] 当前分支不是主干
- [ ] 已执行 `git diff --name-only <base>...HEAD`
- [ ] 已从实际 Git toplevel 执行 `python3 tools/check_capability_contract_alignment.py --base-ref <base>`，确认 Git 环境未重定向、anchor/directive grammar 合法，tombstone 未删除/复用；base/HEAD 的 legacy/current request row 精确同宽，legacy row 独立规范化，current row 逐字段保留 base 有序前缀且只追加合法 tail row
- [ ] “变更范围”与实际 diff 一致
- [ ] PR body 不包含历史草稿、旧分支名、未落地计划
- [ ] 已按 `TESTING.md` 完成测试与测试记录
- [ ] 用户可见变化已对照 `interact.md`
- [ ] 架构变化已对照 `architecture.md`
- [ ] 每轮 review / 修复都已写入“Review / 修复记录”
- [ ] 同类返工已用字段值、行形状、位置、schema、持久化重读、transport actual fact 与资源上限维度的负例矩阵验收，不只记录单点 PASS
- [ ] 若改变 source/artifact terminal publication，已运行 snapshot provenance 专项与独立 checker
- [ ] 若改动 source closure/生成 artifact，terminal artifact 已独立提交或按单 commit 政策 amend 折叠；最终 PR HEAD 与受测 source tree 等价且 snapshot checker PASS
- [ ] 若修改文档体系，`AGENTS.md` 仍能发现 `SOP.md`，SOP 稳定编号与核心权威入口未被无替代删除
- [ ] 对漂移文档的处理是就地纠偏，或已明确记录拆分/历史化的替代入口、兼容路径和理由
- [ ] Issue #15 冻结正文与冻结评论未修改或删除
- [ ] 缺任一 Done gate 时 PR 保持 Draft、body 第一行使用 `Progress on #15`，未写 `Closes #15`

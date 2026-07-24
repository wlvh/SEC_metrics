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

如果新增“能做 / 不能做 / 必须追问 / 必须拒绝”的声明，请确认它有 capability_contract.json anchor_id 或对应测试锚点。

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
- report 或 manifest publication failure；
- light package 缩小声明 source closure。
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

回滚方式：

-

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
- [ ] 同类返工已用字段值、行形状、位置与 schema 维度的负例矩阵验收，不只记录单点 PASS
- [ ] 若改变 source/artifact terminal publication，已运行 snapshot provenance 专项与独立 checker
- [ ] 若修改文档体系，`AGENTS.md` 仍能发现 `SOP.md`，SOP 稳定编号与核心权威入口未被无替代删除
- [ ] 对漂移文档的处理是就地纠偏，或已明确记录拆分/历史化的替代入口、兼容路径和理由

<!--
PR body 原则：

1. 只写本 PR 已经完成的事实，不写计划。
2. 文件清单必须来自：git diff --name-only <base>...HEAD。
3. 测试策略与测试证据记录方式以 TESTING.md 为准。
4. 用户可见变化对照 interact.md。
5. 架构变化对照 architecture.md。
6. 每轮 review / 修复都必须写入“Review / 修复记录”。
-->

## 1. 背景与目标

---

## 2. 实现方案

<!--
写核心思路和关键取舍。
不要复述所有代码。
-->

---
## 3. 变更范围

<!--
必须来自：
git diff --name-only <base>...HEAD

只列本 PR 实际改动的文件或目录。
不要写当前 patch 中不存在的文件。
-->

| 文件 / 目录 | 变更类型 | 说明 |
|---|---|---|
|  | 新增 / 修改 / 删除 |  |

---
## 4. 文档影响

<!--
只写受影响的文档。
如果没有文档需要更新，写：无。

如果本 PR 改变能力边界，请检查 capability_contract.json / interact.md / docs/business_user_guide.md。

如果本 PR 改变用户可观察行为，请检查 interact.md，并判断 docs/business_user_guide.md 是否需要同步。

如果本 PR 改变业务人员能问什么、怎么问、结果怎么看、什么时候该找人，请检查 docs/business_user_guide.md。

如果新增“能做 / 不能做 / 必须追问 / 必须拒绝”的声明，请确认它有 capability_contract.json anchor_id 或对应测试锚点。
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
不能用 quick unittest 代替 Golden、repair gate 或完整场景。
未运行项必须说明原因、影响和对应 caveat，不得写成 PASS。
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

# 限定独立审阅：需要修复一项 P2

审阅精确范围：`f51d8c3d27f3169b9cdb3a246295830882240c1f → 31b74980b936e89934023408e96573bdc392db5f`。工作目录为 `/Users/lyuhongwang/.codex/worktrees/issue28-c03-release/SEC_metrics`。已确认四个审阅文件的当前字节与 head 完全一致，且两个实现文件的 SHA-256 与 saved-proxies.json 所记执行字节一致。结论只覆盖该差异；不授予公司内容、原件真实性重新验收、消费者接线、历史首次披露选择、生产或正式采纳信用。

UTC 开始：2026-10-10 12:02:48 UTC。
UTC 结束：2026-10-10 12:07:14 UTC。
实际工具量：8 次 functions.exec，16 次嵌套工具调用（2 次时钟、13 次 exec_command、1 次 apply_patch）；保守相加共 24 次，低于 80 次上限。
普通消息共 3 条，含首次说明、一次发现更新和最终报告；未提问。时间低于 90 分钟，未触发上限停点。

## P2：季度及日期版 PeoMember 被当作另一名具体人员

位置：`scripts/vnext/governance_signals.py:263–265`；相关新增接线为 225–227 行，以及 180–186 行。这里最后构造 `people` 集合时，两处 `PeoMember` 通用成员的排除仍使用旧的年份正则，而此前概念、人员姓名及 IndividualAxis 已采用 `YEAR_QUARTER_OR_DATE`。

`ecd:PeoMember` 表示通用 PEO 身份，原有测试明确允许它与同一金额的无维度重复值、一个具体人员成员共存。新增政策接受 ECD/2022q4 或 ECD/2022-10-31 后，这个通用标签会留在 `specific_person_members` 中；它与 `ex:PersonAMember` 一起令 `len(people)>1`，产生 `C03_MULTIPLE_REPORTED_PEOPLE` 和 null。三个事实都是当前主体、同一期、USD 100，且实际只有一个具体人员，因此这属于新增路线的误拦截。

独立最小反例使用原测试的 `source`/`arguments` 和新增测试的 `released_source`，只改变版本名：

```python
rows = [
    {'amount': '100'},
    {'amount': '100', 'person': 'ecd:PeoMember'},
    {'amount': '100', 'person': 'ex:PersonAMember'},
]
for release in ('2025', '2022q4', '2022-10-31'):
    raw = released_source(rows, release)
    answer = resolve_c03(**arguments(raw),
                         sec_namespace_release='YEAR_QUARTER_OR_DATE')
    print(release, answer['selection']['reason_code'],
          answer['result']['value'])
```

实际结果：

| SEC ECD/DEI 版本 | 原因码 | 数值 |
| --- | --- | --- |
| 2025 | PASS | 100 |
| 2022q4 | C03_MULTIPLE_REPORTED_PEOPLE | null |
| 2022-10-31 | C03_MULTIPLE_REPORTED_PEOPLE | null |

完整结果见 `generic-person-reproducer.log`。32 项现有测试没有覆盖“显式新版本 + 通用 PeoMember + 同金额具体人员”这一组合，所以全部通过不能消除该问题。

建议两处通用 PeoMember 判断复用同一有限 `sec_taxonomy(p[0], 'ecd')`。默认 YEAR_ONLY 仍采用原判断范围；显式政策才扩展该范围。补充季度、日期反例，并保留同金额两个具体人员拒绝、外国命名空间不能冒充通用人员等控制。此建议未在本次审阅中改源码或测试。

## 其余验证与支持程度

指定命令实际执行：`PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_c03_sec_release tests.vnext.test_governance_signals tests.vnext.test_xbrl_namespace_policy`。Python 3.14.7；32 tests，0 failures、0 errors、0 skips，0.067s，exit 0。日志为 `required-unittests.log`。CI 新增步骤显式列出三个模块，并设置禁写 pyc 和 scripts:tools 搜索路径；本审阅没有网络查询或声称 GitHub CI 已通过。

从指定 base 提交通过 `git show` 读取原源码，在内存中原样执行，未修改其代码，也未使用字节码改写、导入平台或安装框架。用 15 种小输入 × 三种版本完成 45 次完整返回/异常比较，head 的默认行为与 base 完全相等。YEAR_ONLY 默认不增加 selection 字段，旧记录形状、哈希和拒绝新版本行为保持。

额外显式版本矩阵覆盖 45 个输入并完成全部 45 次完整重放：单一人员正向、同金额两个具体人员、不同金额多人、错误主体、非人员维度、错误期间、EUR、假货币命名空间、损坏竞争事实、nil、非批准数字变换、actually-paid 替代概念、同成员冲突姓名以及有完整姓名关系的历史零占位。除上述通用成员反例外，观察到的业务限制保持；两个具体人员即使金额相同，三种版本都仍拒绝。历史零占位只有原有关系充分时才排除，未新增“取非零”规则。

八项源/输出变更控制均拒绝：原件字节、company、scope、expected CIK、SourceReference raw_asset_id，以及记录中的政策、候选引用 ordinal、结果数值。政策、引用及数值变更均为 C03_SOURCE_REPLAY_MISMATCH。完整重放从传入的原件及政策重算；没有从待验证 resolution 自行信任政策。所有显式矩阵输出保持 business_calls=[0,0,0]、formal_publication_authorized=False。结果见 `differential-boundaries.log`。

命名空间辅助函数通过 24 个 http/https × DEI/ECD × 年份/四季度/日期形态的正例、16 个外域或尾缀等反例、4 个不支持 taxonomy 的拒绝。FASB 函数实现未变，原三项 FASB 回归通过。日期部分只核验版本字符串形态；这些验证不证明任意名称是官方发布版本或来源是真实 SEC 原件。识别版本形态无需扩建官方版本注册表来处理本次 P2。

## 边界与文件保护

实际读入参考只为本目录 README.md 和 saved-proxies.json；saved-proxies 的四份真实材料执行属于作者证据，本次仅核对处理代码哈希，没有重读大原件或重复真实执行。不触碰 #47 工作目录、账本、状态或旧审阅，不作网络/真实调用，不 spawn，不打包 tar，不 commit/push，不编辑源码或测试。C03 补丁未修改 C04 业务实现，指定命令中的八项 C04 回归也通过。

仅在本 independent-review/ 目录写 conclusion.md 和三份必要日志。开始时 foundation-compatibility.log 已存在工作区修改；后续只读状态显示 README.md 也由并行工作发生变化。本次未编辑它们，且最终四个审阅文件字节仍绑定指定 head。


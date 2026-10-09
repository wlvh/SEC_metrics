# D03 来源解释与内容核验

当前开发入口沿同一后继调用策略、官方 DeepSeek transport、WB-3 和固定总账执行。它支持原始解释和对既存候选的一次单独内容核验；尚未生成 D03 原生 Result、独立代码审阅或正式验收信用。

`r6_regulatory_semantics` 复用全部年报/修订正文、原生事实和续接对象。语言命中只产生必须评估的索引，不删除其余来源，也不证明未披露。模型选择来源条目，程序提取该条目的完整原文；原始模型响应与程序生成的引文分别保存。

发生日期和披露时状态分开记录。日期可以使用原文形式或相同精度的 ISO 年/月/日；程序定位对应原文，保留实际措辞及位置，不从财年推断事件日期，不把已知月份降为年份。日期与哪个行动相关仍需要语义核验。收到文书不自动证明被调查对象，也不证明调查仍在进行。

当前 v6 的 `context_only_source_indices` 与 finding 引用互斥；标题和一般风险可以明确列为上下文，仍由程序展开为待核验提议。明确披露“目前涉及多项政府调查及执法程序”属于当前事实，不要求材料同时列出案名或案件数。行政环境修复和解本身不能证明 D03 监管调查。

`r6_semantic_verification` 从固定总账读取原调用，核对不可变终态证据，并按原请求绑定的政策重新验证响应。它检查每个提议的分类、主体、发生日期及披露状态；上下文选择也不能绕过检查。原响应仅作为明确绑定的核验输入，不被换绑为新执行响应。存在不支持/未决项时 CLI 返回2；这不是独立代码审阅，不产生 D-06 正式批准。

```bash
python3 tools/vnext_continuous_semantic.py prepare --company pfizer --metric D03 --output /absolute/new/requests.json
python3 tools/vnext_continuous_semantic.py execute --company pfizer --metric D03 --request-id <prepared-id> --output /absolute/new/result.json
python3 tools/vnext_continuous_semantic.py verify --company pfizer --metric D03 --prior-call <ordinal> --output /absolute/new/check.json
```

真实执行必须有当前版本的离线接线材料及进程环境中的凭据，累计次数仍受批准的240/240/80控制。上述命令不是可随意重复的回归测试。模型语义反馈和明确工程修复后才能安排必要的不同请求；原失败和调用次数永久保留。

验证材料在 `docs/evidence/issue28_continuous/regulatory-*`。模型曾把标题当事实、混淆历史事件与仍在继续的状态；第一次内容核验只抓住部分问题。Pfizer 修后样本和 JPM 留出样本分别记录，不能用前者替后者取得信用。当前还需完整材料解释、D04真实正向/历史对照、原生 Evidence/Review/Run、390和独立模块审阅。

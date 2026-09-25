# E01 的 8.01 关键词分支：从未读过 8.01 正文

## 定义怎么说，路线实际做了什么

已批定义（`02_指标定义_SEC_10公司单年指标.md` E 节）：E01 "M&A announcements" 计 8-K 的 1.01、2.01、8.01 三类，并注明"8.01 需正文关键词确认"——8.01 要靠正文里的关键词确认才算。

路线把关键词拿去和每条 claim 的 `brief` 比。只要申报的 hdr.sgml 带 item 代码（本帧七个窗口里每份都带），`brief` 就是固定文字 `8-K item 8.01 parsed from hdr.sgml`——里面不可能出现 merger/acquisition/combine/transaction。所以 **8.01 分支一份都没放行过**，已发布的 E01 实际只是 1.01 与 2.01 的条数。首页正文（`primary_heading_brief`）其实已经算出来了，只是从来没拿去匹配。路由器被 `issue_28` 各世代按字节冻结，普通路线也用它，行为一样。

## 读了什么

`tools/read_e01_eight_o_ones.py` 不复用路线的文本取法，直接从已保存的主文件读：按申报自己的标题定位 8.01（"Other Events"，Pfizer 那份写的是"Results of Other Events"），读到 Item 9.01 或签名为止。七个有值窗口共 **23 份 8.01，全部整段读过**，每份的判断记在 `eight-o-one-judgements.json`（判断的是"这一项是否报告了注册人或其子公司参与的合并、收购或业务合并"，逐段读，不看关键词命中）。

- 23 份里**只有 1 份**报告了交易：Pfizer 2025-11-13，完成对 Metsera 的收购（"completed the previously announced acquisition of Metsera, Inc. … pursuant to the Agreement and Plan of Merger"）。
- 8.01 正文里带关键词的有 4 份，只有 Pfizer 这份是交易；另外 3 份是融资：Marriott 两份的募资用途句"may include … acquisitions"，Macy's 要约收购的"combined aggregate purchase price"。
- 另有 5 份关键词只出现在别的 item 里（Item 1.01 的契约条款"merger or consolidation"/"corporate transactions"，Item 7.01 的"repricing transaction"）。

**这次阅读自己也先错了一次**：第一版只认"Other Events"标题，Pfizer 那份读成空、零关键词——和路线的漏法同形，只是高了一层。

## 各口径下的计数（路线自己的单位：每个命中 item 计一次）

| 位置 | 已发布 | A 保持现状 | B 8.01 正文字面命中 | C 正文命中且确为交易 | D 全文字面命中 | 结论 |
|---|---|---|---|---|---|---|
| Enphase 2025 | 0 | 0 | 0 | 0 | 0 | 接受 |
| Ford 2025 | 2 | 2 | 2 | 2 | 2 | 接受 |
| Southwest 2025 | 2 | 2 | 2 | 2 | 2 | 接受 |
| Lumen 2025 | 7 | 7 | 7 | 7 | 11 | 待决定 |
| Macy's 2026 | 2 | 2 | 3 | 2 | 4 | 待决定 |
| Marriott 2025 | 0 | 0 | 2 | 0 | 2 | 待决定 |
| Pfizer 2025 | 0 | 0 | 1 | 1 | 1 | **已登记缺陷** |

接受规则：只有已发布值在 B、C、D 三种"读正文"口径下都成立时才接受——即结论不依赖还没做的决定。Pfizer 在所有读正文的口径下都是 1，只有"8.01 永不计入"（A，等于删掉定义里那一条）下才是 0，所以按现行定义它是错的，登记为 `E01_PFIZER_2025_EIGHT_O_ONE_BRANCH_NEVER_READS_THE_ITEM`，按坐标撤回。

## 缺的是哪一个含义判断

**一份 8.01 只在融资语境里用到关键词（募资用途列表里的 acquisitions、要约收购的 combined 金额），算不算一次并购公告？** 已批的匹配方式（正文任意位置子串命中）说算，指标名字说不算；本语料里带关键词的 4 份 8.01，两者在 3 份上意见相反。附带一个小问题：同一份申报里别的 item（1.01 契约条款、7.01）能不能替 8.01 确认。

选项与推荐见 `decision.json`：推荐 C（关键词须指向一笔具名交易：`acquisition of <名称>`、`Agreement and Plan of Merger`、`merger with <名称>`；列表里的复数、形容词不算），因为它是唯一一个让本帧每个计数都等于申报实际内容的口径。代价：它是新的匹配方式，要按既有修订机制改已批路线规则，在 #47 自己的后继规则文件里实现（与 D01 下划线修复同一做法，冻结路由器与普通路线不动）；正例只有一个真实实例，所以实现必须把每一处被它拒绝的关键词命中记录下来而不是静默丢掉，漏判才看得见。

## 顺带记下、不在本次决定范围内

定义让 1.01 不经确认直接计入 E01。七个窗口里 13 个 1.01：**11 个是借款/债券协议**，1 个是 Southwest 与 Elliott 的合作协议，只有 1 个（Lumen 把光纤业务卖给 AT&T）是并购。路线在 1.01 上完全按定义办事，所以这是定义本身的问题，不是缺陷；E05 就是 1.01 的计数。如果 owner 想让 1.01 也只计并购，Ford 会是 0、Lumen 1、Macy's 0、Southwest 0。记录，不提议。

## 不主张

E01 以外的指标；本帧其他期间（往年 8-K 正文未保存）；定义本身是否回答了业务问题。零新增调用。

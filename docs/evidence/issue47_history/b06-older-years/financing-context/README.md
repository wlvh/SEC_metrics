# B06 完整来源上下文开发：Macy's FY2024

日期：2026-10-04。沿用 `37a38d2f` 正常历史来源探针保存的同一份
10-K（期末2025-02-01，提交2025-03-21，accession `0001628280-25-014315`）。
本增量没有新的自然语言选择规则，没有接入运行，也没有新增调用、Run或接受。
原B06仍为NONE/WITHHELD、value=null，接受登记909不变。

## 已定位的开发缺口

此前期限栏修复已支持21个原生成员、27.79亿借款及另列0.15亿融资租赁组件。
完整范围仍停在 `STANDBY_CAPACITY_NATURE_UNPROVEN`。执行者阅读MD&A
B560–597、Note6 B1335–1347及必要租赁/购买承诺段落后确认：所需额度关系在
MD&A B568，旧附注句法输入没有带上这处关系，不能把程序拒绝说成原件未披露。

| 原件关系 | 开发参考及边界 |
|---|---|
| B568 | ABL上限30亿−备用信用证1.44亿=借款额度28.56亿；再受存货借款基数限制3.97亿，可用额24.59亿。额度、可用额和期末借款余额分别保留。 |
| B590、B1338 | 本年借入并归还3.01亿；两个年末均无ABL借款。流量不加为期末负债。 |
| B1340 | 另一个银行协议两个年末均无循环贷款；其上限原文字面为100万美元，原样保留，不擅改为10亿或与ABL合并。 |
| B592、租赁表 | 融资租赁未来付款2300万−利息800万=账面1500万；当期200万＋非当期1300万相符，未来付款不重复加入。 |
| B1163 | 非当期融资租赁内含100万非租赁组件，保留公司已报告分类，不另加或扣除。 |
| B575、B1762 | 29亿商品/服务购买承诺，收到商品或服务时确认负债，不直接视为额外借款。 |

`executor-source-reference.json` 保存7项有限开发判断、36个原字节引用、两张
完整必要租赁网格及8对HTML/XML原生事实。引用逐一核对原始字节范围与SHA；
维度顺序不同按完整解析QName集合比较，原顺序不改。首版参考打包器将维度列表
顺序当作身份而失败，未产出参考；改为上述集合比较后通过。没有全读2140块或
为每源135个候选完成语义分类，没有整份B06或各媒介完整性信用。

为诊断下游，`downstream-reference-probe.json` **仅向一个旧库存函数手动提供上述
参考操作数**，复用已有组件，绕开上游解释，不生成scope proof或业务对象。
真实原件在primary ordinal833、c-152的官方 `LineOfCredit` 被
`C03_ZERO_TRANSFORM_TEXT_CONFLICT` 拒绝；`downstream-failure-trace.json`保存定位。
原文是`no`，官方2020-02-12 `fixed-zero`，USD/current instant；XML同事实是0，
B1340也明确无循环贷款。ordinal829的ABL原生事实也是`no`，旧库存已有仅该
concept的有限分支。这是零值解析开发缺口，未靠修改原件、手补值或放宽原检查器解决。

## 来源准备及可复核边界

`prepare_source_packet.py`禁网执行，沿现有正常B06保存来源准入重建，再逐字核对
primary/XML与先前capture的raw blob及source reference。年度准备自己的proof列表
不含XML；首个错误假设被守卫拒绝，修正为重建完整B06的正常input binding，
没有把XML伪加到年度proof或跳过准入。

保留全部2140个B文字块、108张表/21099展开格及每源135个当前潜在融资原生事实。
文字和表头/网格关系沿现有表示全量比较相同；候选概念类不等于完整融资范围，
未自动赋予语义角色。原数值解析错误保留null及错误名。

第一版来源数据参考计量172708 token，保存的metadata与重建收据带`-v1`；
第二版增加原`format`和`xsi:nil`的解析QName证据，数据参考计量176767。
没有增加或删除原文/表格/原生候选。两版本均不是完整模型请求，没有提示或输出合同，
不能由此声称可发送、provider计量或开发模型通过。第二版7份输出在新目录重建
逐字节相同，见`fresh-rebuild-v2.json`。原第一版输出不覆盖，来源原件不提交重复副本。

```bash
python docs/evidence/issue47_history/b06-older-years/financing-context/prepare_source_packet.py \
  --capture <既有正常capture目录> --source-root <restore后的认证source-inputs> \
  --out <全新输出目录>
python docs/evidence/issue47_history/b06-older-years/financing-context/build_reference.py \
  --packet <上述输出目录> --capture <同一capture目录> --out <全新参考文件>
```

下一步先完成必要融资事实参考和固定输入任务，再按#28 §5.8做独立输入验证；
若方法成立才做接入及对应DeepSeek验收。当前没有独立B06回答或新的调用许可，
原35次模型许可已经用完，SEC余96仍须所有者resume。

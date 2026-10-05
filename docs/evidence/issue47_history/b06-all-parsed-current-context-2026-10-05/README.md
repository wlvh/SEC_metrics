# B06：保留全部解析期末事实及隐藏的报表归属说明

原完整问题 `9feffb12…aee951e` 提供2140文字块、108表及每源153候选，候选本身不证明融资完整性。此前已确认144个额外期末USD金额仍在原正文/表格中；本次没有把它们描述为金额来源被删掉。

从同一已校验capture重读每源1555解析事实，固定期末2025-02-01，保留每源 **336个解析期末事实**：258个USD金额及78个其他单位/非金额事实。原153个候选的全部12字段逐项完全相同。新增加183项中，144个USD已在前一清点逐项读完，本次另外39个非USD原生行在两个完整分包读完，没有按融资关键词删选。

原生中的非金额字段有实际用途。primary7/9、12/13、16/18是隐藏的报表归属说明：

- 融资及经营租赁ROU资产都指向 `m:LeaseRightOfUseAsset`；B846和原生158/548报告2243million合计资产。共同位置不把整个合计认定为融资租赁资产，更不加入债务。
- 当前融资及经营租赁负债都指向 `us-gaap:AccruedLiabilitiesCurrent`；B855和原生172/944是2625million Accounts payable and accrued liabilities。融资当前2million有原生550支持；归属说明是“列在哪个栏”，不是第二个金额，也不表示2625全部融资。
- 非当前融资及经营租赁负债都指向 `m:NoncurrentLeaseLiability`；B859和原生180报告2927million Long-Term Lease Liabilities，与B861/原生184的Other Liabilities902million分别列示。融资非当前13million有原生554支持，不凭泛称把它放入Other902另加。
- primary22的supplier-finance报表栏枚举在HTML隐藏标签和解析XML中均为空，原raw片段已核验，不补一个猜测指针，也不解释为空借款或零值。

六个非空归属URI没有进入原9feff问题，原隐藏标签及字节跨度/SHA另存。这是必要原生说明的补充，不是改写原请求或授完整融资信用。Other902的完整性质、interest48million归属及完整融资集合仍未证明，总额/ratio仍NONE/WITHHELD、null。

对全部336对象使用原金额转换器作诊断，得到primary17/XML16个未归一化项，均属非USD/非金额：资产或租赁年限、枚举URI、primary文字one的投票数等。它们不是17个债务金额失败，也不证明非数值原件无效；258个USD金额仍全部可按原历史转换器归一化。诊断保留实际错误，不改#28检查器、不增加金额转换白名单。新增shares、USD/share、比例、州/店铺/票数及资产年限都保留本身单位，不指定融资角色。

只准备两个有界源输入表示，原任务、批准定义、输出合同、模型参数、原200000/4096限制以及全部原正文/表格表示不改：

| 表示 | 输入token | 加原4096后 | 结果 | 精确请求SHA |
|---|---:|---:|---|---|
| 336×2完整字段直接展开 | 295191 | 299287 | 超限，保留失败 | `eb68c20f5ca14019a811276150dca8b6dcdea3e459fe702bffb98a43a573458d` |
| 共享完整字段值 | 188798 | 192894 | 符合原上限 | `bdad31f0dc7b55a5f49f9308c74168b41dd44ee8748156bdfeeabc1ffa7a1966` |

共享表示是每个原字段值只存一次，源顺序的每行以索引引用；`fields[j]` 与 `values[row[j]]` 恢复原字段。完整context、unit、attribute和literal字符串保留，false/null类型区分，不把值字典索引当原生ordinal，不合并不同事实。输出仍引用原source_kind/ordinal。336只描述既有解析器的期末人口，不宣称全部raw native universe、各媒介解释或债务完整性。

`prepare_complete_native_request.py`只读取原精确请求和新来源清点，没有参考或旧回答输入；正文/表格对象逐字段相同、原153对象完全保留、全部336字段往返相同。系统追加的是来源解码和金额诊断边界说明，没有答案或手工操作数。尚未独立模型验证或接入正常运行。五个内存反例（字段顺序、越界索引、布尔索引、少一源行、改context值）分别由解码结构检查或与完整原对象对照检出，不冒充原生Evidence gate。

21成员归档经字节/SHA和安全解包验证；从原capture重新清点的四输出、从解包输入重建的两请求/计量及proposal共九输出逐字相同。原capture见已提交 `evidence/issue47_local_inputs/b06-financing-v3.tar.gz`。清点的prior候选参数可从本包 `original-request/request-body.json` 的user对象中原样恢复 `current_potential_financing_native_facts`，不依赖虚拟机路径或先前临时source-v4目录。

原9feff及其已提出的单次只读权限对象保持原义；新bdad是另外一个具体开发问题，未获得子代理或真实调用许可，不能拿旧问题的单次许可自动执行它。新增DeepSeek/paid/SEC `[0,0,0]`、新Run/接受0。原模型包、旧Run/答案/失败、来源字节及104缺陷对象不改。

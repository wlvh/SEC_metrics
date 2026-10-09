# Pfizer 历史同比的有限原件范围核对

本记录承接已发现的B02 FY2021/2023/2024三个DIFFERS，不新增抽取方法/模型请求或银行范围。生产修订PR116保持原范围；本纯证据分支从main f6开始，只保存后继原件核对与现有合同消费者结果，不另开准备helper/控制器/renderer或新PR。

通过原年度选择/来源读口取得当前与原前期primary，再用现有原生事实解析、USD/context/主体检查读指定未分维度收入事实。没有把当前申报的prior列伪装成原前期申报；两种都分别保存其accession角色、原始context、ordinal、源SHA及SourceReference。来源只读、socket禁止，模型和指标计算为零。读取代码执行在PR116同消费者树上，公共解析器字节同main；记录分支只携材料，不将资料提交当代码验证。

| 年度 | 当前概念/数值（十亿美元） | 当前申报的前期栏 | 原前期申报 | 含义 |
|---|---|---|---|---|
| FY2021 | 客户合同收入税外81.288 | 同概念2020=41.651 | 同概念2020=41.908 | 同标签但前期金额重列；现配对内核同概念直接继续，不证明同范围可比 |
| FY2023 | 客户合同收入税外50.914；另列总收入58.496 | 客户合同收入2022=91.793；总收入100.330 | 总收入2022=100.330 | 原先选当前客户收入/原前期总收入，不是同一收入范围 |
| FY2024 | 总收入63.627 | 总收入2023=59.553 | 客户收入2023=50.914；总收入58.496 | 标签桥不能证明所选原前期金额相同，且当前前期总额有重列 |

原3个read/published差异已在statement continuation主记录保留。本记录不任选一个读数替换另一项，不改原事实/旧Run/旧失败；尤其不因同concept让FY2021自动取得业务接受。公共paired_measure_v1由#28维护，具体原件/反例已直接交付；需要明确现行“原前期角色且同量可比”的检查对同概念重列如何处理，不写竞争内核。

现有合同对FY2023/FY2024的真实公司结果已验证：在原Pfizer任务只新增B02两位置，首16.739s/exit2，均HISTORICAL_PAIRED_MEASURE_NOT_COMPARABLE/WITHHELD/null；input-assessments保原两角色金额及目标申报桥未相等。禁factory稳定复1.285s/exit2/calculationfalse，另进程results .545s/exit0；原十五B01/B04/B05正确值及文件保持，保存读口共17结果。pfizer-b02-withheld-company.json/log。这两项是明确扣留，不是正确增长率已交付。FY2021待公共同概念可比修补，FY2022/FY2025还有已有MATCH参考待入口处理；完整责任继续。

材料可从PR52已提交SEC导出恢复，使用实际source-inputs根。所有新来源/模型/paid调用0，无NativeRun/接受/Ready/merge/发布/active。原后继proof与源ordinal足够定位，不再制造审查包或重读整个年度。

## 原表进一步发现的B01范围缺陷

PFIZER FY2023实际table_000113列Product revenues50,914m、Alliance revenues7,582m、Total revenues58,496m；原CFC概念对应Product而非total。同申报其他三张范围表的总额也为58,496m，pfizer2023-revenue-tables.json保原表行/头、原native fact ordinal/context、SourceReference与SHA。这说明仅两个来源数值相符不足以给B01全范围接受。先前statement consumers中的FY2023 B01新Result与旧参考同50,914m，但现在登记具体subtotal-scope缺陷，不能继续称该位置正确。pfizer2023-b01-scope-defect.json及optional-reader defect list定位新Result，不改旧Result/Trace/回答。其他年份或#28当期不按类推判错。

原件同时明确2021 Meridian的财务结果按终止经营重列所有列示期间，以及2024把原royalty income从Other income转入Total revenues、前期重列；source-block定位保在pfizer-presentation-scope-text.json。FY2021相同concept不能证明同范围，FY2023分量/总量以及FY2024 royalty范围也不能换prior数据凑算。公共配对/收入core修由#28负责，具体材料已直接交回；这不是新取值政策或放宽检查器。

精确缺陷读取已用公共现有--defects-file接口验证，原Pfizer task独立results不算源/不计算：FY2023 B01 value空、WITHHELD_KNOWN_DEFECT/CONFIRMED_INVALID，原ResultID保；其他十四原值和两个B02扣留仍可读，141原结果/pointer文件哈希保持。pfizer2023-known-defect-read.json给输出和精确ID。缺陷清单只是新显示hold，不是替换事实、手工正确值或接受；公共默认登记尚待#28接收，未传此清单的旧读口仍会显示原值，不隐瞒这一边界。

## 不受争议年度阻断的两个同比消费者

原FY2022/FY2025的native current/prior对照已补：2022当前Revenues100.330bn，当前比较栏Revenues81.288bn与原2021CFC81.288bn相等；2025当前Revenues62.579bn，当前比较栏和原2024Revenues均63.627bn。原表2022总收入行100.330/81.288；2025分别Product51.663、Alliance9.266、Royalty1.650，Total62.579，同口径2024总额63.627。pfizer-supported-native-revenue.json与完整选定表证明金额、unit/context/源SHA与全部收入范围，不再仅凭旧MATCH。

现有公司task只新增两个B02缺位：FY22首9.128s、禁止factory复.895s；FY25首6.611s、禁止复.905s；新目录独立read.545s。值分别.2342535183544926680444838106及-.01647099501783833906989171264 ratio，各全年窗口，同来源/独立原件参考。原141结果/pointer文件保持，无邻居重算；现有defect清单使FY23B01仍空、23/24B02仍WITHHELD，21B02未处理不借此接受。

首次驱动误向run传--defects-file（仅results支持），参数解析阶段拒绝、未处理财务或调用；失败日志保，修正只在独立results传入，未改公共CLI。真实两个首跑在原statement消费者f79树执行，当前分支只携后继证据且生产零diff；不把证据分支当另一版本算法或新pipeline。公共同概念重列/完整收入选择及默认缺陷登记继续待接收，材料充足但缺核心支持的路径不取消责任。

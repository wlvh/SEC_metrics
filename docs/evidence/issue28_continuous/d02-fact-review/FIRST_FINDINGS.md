# D02 新事实核验初轮独立复核

受审4文件及始末hash见 probe-result.json；作者随后确认相同hash。本轮只生成TEST_ONLY源副本和原生Evidence/Review/Result，没有Run、source admission、V13验收或正式发布信用，provider/paid/SEC=0/0/0。

## 实际问题

1. 单一ISO4217 namespace仅配三个大写字母就授 VERIFIED_AS_REPORTED_MONETARY_FACT。undefined_currency_ZZZ 原副本产生 reported_currency=ZZZ、value_normalized=107000000；来源声明了字符串，不等于当前实现已支持并核验该货币。推荐明确当前支持的货币，其余保留SOURCE_LITERAL_ONLY，不宣称币种本身无效。
2. 无 format 的原文1,23得到value_normalized=123000000，保留原件里无格式转换的事实，却复用了会去除所有逗号/空格的数值parser。推荐限制已支持的XML decimal词法；未支持语法保留原文和值未核验状态。

numdotdecimal + 1,23 同样得到123000000，本报告将其记录为支持语法边界观察，未在缺少transform规范证据时断言它一定违反该transform。作者决定明示当前仅支持严格三位分组的保守子集；不把其他格式宣称成源数据错误。

## 已通过的边界

numcommadecimal明确SOURCE_LITERAL_ONLY/value_normalized=None并保留1,23，不能显示123M；假transform URI、假ISO4217 namespace、错误CIKscheme保留原文且不授金额；伪fasb URI不成为合法us-gaap候选。旧2023期间不重标2025；另一CIK保留OTHER_ENTITY_AS_REPORTED不算本公司本期。EUR正例保留EUR，不转换USD。合法本期107M补充事实在Review中显示，最终仍TEXT_V1，未阻断文字，也没有生成总诉讼负债。

每例的 TEST_ONLY_source.htm、review.md、evidence.json 均保留。probe-result.json 是初轮结果，不随修复覆盖。修后将直接读取这些原副本进行新目录重放。

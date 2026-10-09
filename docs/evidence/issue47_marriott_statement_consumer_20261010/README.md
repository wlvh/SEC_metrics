# Marriott 早年营业收入消费者接续

本批使用实际main f6ef7886既有B01公司入口，生产代码零改动。只新增此前未交同公司任务的FY2021–2023三个收入位置，不重跑既有两年B01、酒店/原文全帧、FY2024混合B04或其他family。输入沿原full-source余额任务，source-root身份不变；旧十个B08/B09结果保持，未复制源/program树或改公共controller/store。

复用PR52已提交cross-source-read-batch的原件阅读、source SHA、值/单位和实际年窗，existing-reference.json保必要三项及原参考SHA。各年B01为13,857m、20,773m、23,713m USD，实际1月1日至12月31日，来源金额及原生年度按现有shared source检查，source/socket禁止网络。旧Run/接受ID不是本次信用，业务范围仍按原定义，后继范围缺陷不能因MATCH自动豁免。

同公司run一次范围FY2021–2023首14.891s三READY；禁止原factory复1.591s/计算0、独立results .520s，原余额80文件及新旧107结果/pointer文件字节保持（实际数量以actual-company.json为准），三值/单位/日期全部同参考、十余额仍读。没有重新准备酒店、旧收入位置或更换source-root。源码在未提交材料时运行，program_version保has_uncommitted_changes，不以材料提交重签结果。

```bash
python3 tools/vnext_company.py run --company marriott_international --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2023 --metric B01 \
  --source-root /saved/sec/source-inputs --work-dir /existing/marriott/state --output-dir /new/marriott/runs
python3 tools/vnext_company.py results --company marriott_international \
  --state-root /existing/marriott/state --output-root /new/marriott/read-01
```

已有state必须绑定同一source-root；新任务用外部新目录，results输出须新。首次完整SEC材料恢复用保留历史分支原restore/返回data_root，无新GET。旧任务/结果读自己的身份，不手工拼接结果或造第二renderer。FY2020前期修订影响FY2021 B02仍未接；FY2024/25收入原验证复用，完整统一五年company状态及其他指标继续。此次记录是新普通消费者三位贯通，不宣全部1950/在线来源/业务正式采纳。调用0/0/0，无新Run/Ready/merge/active。

## FY2022–2025同比缺位

同一原task只新增四个B02，首17.751s，禁factory复2.008s计算0，独立results .541s；原107余额/早年收入结果pointer文件及最终139文件保持。值依次.4990979288446272641985999856、.1415298705049824291147162182、.05849112301269345928393708093、.04326693227091633466135458167 ratio，实际完整年度与原独立参考一致。b02-existing-reference/actual-company.json保新旧范围。

本批仍未运行FY2021 B02，其原FY2020修订不能仅按相同收入表解除全部来源限制。原hotel/两年B01/FY2024混合B04不算，未来完整公司状态接续和配对公共增量按实际影响处理。没有新增生产方法或scope取值策略，未给旧Run或历史阅读添接受登记。

## 其余净利润与自由现金流缺位

只新增九位置：B04FY2021–23首13.657s/禁factory复1.301s、FY2025首3.647s/禁复.781s；B05FY2021–25首20.363s/禁复1.850s。独立results .615s，原139文件及最终211文件保持，九值/单位/实际年窗同既有独立原件参考，earnings-existing-reference/actual-company.json/log保原结果和来源。FY2024B04已经在旧酒店混合任务完成，明确不重复该位置；两年B01和酒店全帧也不重跑。

新任务仍非完整全部指标/统一五年接收。FY21B02需公共同期修订属性；旧两年B01和旧B04任务只读原身份，结果汇入普通公司入口不能由本方另写renderer/controller或靠手工改source-root。公共完整收入scope接口就绪后按实际影响消费，不借旧MATCH作为所有来源范围接受。源/模型/paid0，无新Run/接受/发布/active。

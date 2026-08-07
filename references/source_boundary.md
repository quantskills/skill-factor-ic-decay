# Source Boundary

本 skill 只对**用户提供的因子面板**做 IC 衰减与稳定性统计，不预测、不喊单、不接入数据库。

Allowed sources（允许）:

- 用户自备长面板 CSV：`date, symbol, factor, fwd_ret`（及可选 `fwd_ret_{n}`）
- 研究库 / 回测引擎导出的对齐面板
- 在**其他** skill 或脚本中用 Pandadata 等合规取数后拼好的面板（本仓库不内置取数）

Not allowed unless the user has rights and explicitly provides them:

- 付费墙内 / 会员专享行情或因子库的未授权抓取
- 本 skill 内直接写券商 / 私有库连接器、SQL 适配器、自动爬取

## 本 skill 不做的事

- 不提供 DB / API 适配器；不替用户下载行情
- 不构造因子表达式、不做组合回测、不输出买卖指令
- 不做季节性、归因、同业对标（那些是其他 QuantSkills）

## 输出边界

- 只输出：日度 IC 汇总、ICIR、NW-t、滚动稳定性、多周期衰减与半衰期拟合
- 每个结论须标注：因子名、数据窗口、IC 观测数、是事实还是推断
- 必须声明：半衰期与强度标签是历史证据描述，不是保质期或交易信号
- 可选在别处用 `skill-pandadata-api` 等拼面板，再把 CSV 交给本 skill

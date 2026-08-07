# IC 方法说明（ic-methods）

本 skill 只做**截面预测力**诊断：日度 Spearman IC、ICIR、Newey-West 显著性、滚动稳定性、多周期衰减与半衰期。不构造因子、不回测组合。

## 1. 日度截面 Spearman IC

对每个交易日 \(t\)，在当日截面上对 `(factor, fwd_ret)` 做 Spearman 秩相关：

\[
\mathrm{IC}_t = \mathrm{Corr}\big(\mathrm{rank}(f_{i,t}),\ \mathrm{rank}(r_{i,t\to t+h})\big)
\]

- 用秩相关降低极端值敏感度（相对 Pearson）
- 当日有效截面标的数 &lt; 3 则跳过该日
- 数值上强制 \(\mathrm{IC}_t \in [-1,1]\)

## 2. 汇总指标

对日度 IC 序列 \(\{\mathrm{IC}_t\}\)：

| 指标 | 定义 |
|------|------|
| 均值 IC | \(\overline{\mathrm{IC}}\) |
| 标准差 | \(\mathrm{std}(\mathrm{IC}_t)\)（样本标准差） |
| ICIR (raw) | \(\overline{\mathrm{IC}} / \mathrm{std}\) |
| ICIR (年化) | \(\overline{\mathrm{IC}} / \mathrm{std} \cdot \sqrt{252}\)（日度序列） |
| 命中率 | \(P(\mathrm{IC}_t &gt; 0)\) |
| Newey-West t | 检验 \(\overline{\mathrm{IC}} \neq 0\)，默认 lag=5 |

年化 ICIR 假设日度 IC 近似独立；实际 IC 有自相关，故同时报告 **NW-t**，不要只看 ICIR。

## 3. Newey-West t（Bartlett 核）

对 demeaned IC 残差 \(u_t = \mathrm{IC}_t - \overline{\mathrm{IC}}\)：

\[
\hat\sigma^2_{\mathrm{NW}} = \hat\gamma_0 + 2\sum_{j=1}^{L} \Big(1-\frac{j}{L+1}\Big)\hat\gamma_j,\quad
\hat\gamma_j = \frac{1}{n}\sum_{t=j+1}^{n} u_t u_{t-j}
\]

\[
t_{\mathrm{NW}} = \frac{\overline{\mathrm{IC}}}{\sqrt{\hat\sigma^2_{\mathrm{NW}} / n}}
\]

默认 \(L=5\)。重叠持有期收益会抬高自相关，NW 校正方向正确，但 lag 选择仍是经验值。

## 4. 滚动稳定性

默认窗口 \(W=60\) 交易日：

- 滚动均值 IC
- 滚动年化 ICIR \(= \mathrm{mean}_W / \mathrm{std}_W \cdot \sqrt{252}\)

用于看预测力是否阶段性塌陷，而不是只报一个全样本均值。

## 5. 衰减曲线与半衰期

若面板含 `fwd_ret_{n}`（如 1/5/10/20），对每个周期 \(h\) 算全样本均值 IC，得到曲线 \(\mathrm{IC}(h)\)。

对 **均值 IC &gt; 0** 的周期点做 log-linear OLS：

\[
\log \mathrm{IC}(h) = \log A - \frac{h}{\tau}
\quad\Rightarrow\quad
\mathrm{IC}(h)=A\,e^{-h/\tau}
\]

**半衰期**（IC 衰减到一半）：

\[
t_{1/2} = \tau \ln 2
\]

- 若斜率 \(\geq 0\)（未衰减或递增）：不报告正半衰期
- 正均值点 &lt; 2：无法拟合
- 仅单列 `fwd_ret`：报告该周期 IC，半衰期标注为不可估

## 6. 样本护栏

| 条件 | 行为 |
|------|------|
| IC 观测 &lt; 60 | `ValueError`，拒绝输出 |
| 60 ≤ n &lt; 252 | 允许，但 `low_sample_warning=true` |
| n ≥ 252 | 正常 |

## 7. 常见陷阱

1. **未来函数**：因子用了当日收盘后才知的信息，或 `fwd_ret` 对齐错误 → IC 虚高。本脚本不取数，由用户保证对齐。
2. **重叠周期**：`fwd_ret_20` 相邻日高度重叠 → IC 序列自相关强、衰减曲线更平滑，半衰期可能被高估稳定性。
3. **截面过窄**：每日标的太少，Spearman 噪声大；报告须看 `n_symbols` 与每日跳过情况。
4. **把半衰期当保质期**：\(t_{1/2}\) 是历史衰减形状的拟合参数，不是“还能用 N 天”的承诺。
5. **只看均值 IC**：忽略 ICIR、NW-t、滚动塌陷与跨周期衰减，容易把噪声因子当有效。

## 8. 强度标签（非交易信号）

脚本给出的 `strength` 仅作证据摘要：

- `strong`：|mean IC|≥0.03 且 |NW-t|≥2
- `moderate`：|mean IC|≥0.01 且 |NW-t|≥1.5
- `weak_or_noise`：其余

阈值是启发式，用于报告可读性，**不是**下单门槛。

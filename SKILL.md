---
name: factor-ic-decay
description: Diagnose factor predictive-power decay via daily Spearman IC, ICIR, Newey-West significance, rolling stability, and multi-horizon half-life. Evidence-first, no signals. Use when the user asks 因子IC衰减, IC半衰期, 因子稳不稳, ICIR, 预测力衰退, or 因子还能用多久, on Claude Code, Codex, Cursor, Hermes, or OpenClaw.
license: GPL-3.0-only
metadata:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-factor-ic-decay
  repository_url: https://github.com/quantskills/skill-factor-ic-decay
  project_type: skill
  collection: factor-ic-decay
quantSkills:
  project_type: skill
  category: analyst
  tags: [factor-ic, ic-decay, half-life, icir, factor-research]
  platforms: [claude-code, codex, cursor, hermes, openclaw]
  language: zh-en
  status: stable
  validation_level: runnable
  maintainer_type: community
  requires: []
  summary_zh: 用日度截面 Spearman IC、ICIR、Newey-West 显著性、滚动稳定性与多周期半衰期，诊断因子预测力衰减；事实优先，不给买卖指令。
  summary_en: Diagnose factor IC decay, ICIR, significance, rolling stability, and multi-horizon half-life. Evidence-first, no trading signals.
---

```json qsh-form
{
  "version": 1,
  "task": {
    "placeholder": "补充因子名称、面板路径、关心的预测周期或研究问题（可选）"
  },
  "fields": [
    {
      "key": "panel",
      "label": "面板 CSV 路径",
      "type": "text",
      "placeholder": "examples/data/demo_panel.csv 或你的长面板"
    },
    {
      "key": "name",
      "label": "因子名称",
      "type": "text",
      "default": "factor",
      "placeholder": "如 MOM20 / 换手率反转"
    },
    {
      "key": "window",
      "label": "滚动窗口（交易日）",
      "type": "select",
      "default": "60",
      "options": [
        { "value": "40", "label": "40" },
        { "value": "60", "label": "60（默认）" },
        { "value": "120", "label": "120" }
      ]
    },
    {
      "key": "focus",
      "label": "关注点",
      "type": "select",
      "default": "all",
      "options": [
        { "value": "all", "label": "全套诊断" },
        { "value": "half_life", "label": "半衰期 / 衰减曲线" },
        { "value": "stability", "label": "滚动稳定性" },
        { "value": "significance", "label": "IC 显著性" }
      ]
    }
  ],
  "prompt_template": "{{#task}}任务与材料：\n{{task}}\n\n{{/task}}{{#attachments}}用户上传的材料（已放入工作区）：\n{{attachments}}\n\n{{/attachments}}对因子「{{name}}」做 IC 衰减与稳定性诊断。面板：{{panel}}；滚动窗口 {{window}} 日；关注点：{{focus}}。先读本 skill 的 SKILL.md 与 references/ic-methods.md、references/source_boundary.md，再运行 scripts/ic_decay.py，输出中文证据报告（均值 IC / ICIR / NW-t / 滚动稳定性 / 半衰期），事实与推断分离，不给买卖指令。"
}
```

# 因子 IC 衰减诊断（Factor IC Decay）

回答三个问题：**预测力衰减有多快？IC 稳不稳？半衰期大概多久？**

与季节性 / 归因 / 同业对标不同——本 skill 只做截面预测力的时序与跨周期诊断，不构造因子、不回测组合、不喊单。

**输出范围**：日度 Spearman IC、ICIR、Newey-West 显著性、滚动稳定性、多周期衰减曲线与半衰期；事实与推断分离。  
**不做的事**：不输出买卖指令、不保证因子“还能用多久”、不替用户取数拼面板。

## 何时使用

- "这个因子的 IC 衰减快不快 / IC 半衰期"
- "因子稳不稳、ICIR 怎么样、预测力是不是在衰退"
- "因子还能用多久"（只能给半衰期与稳定性证据，不能给保证）

## 输入数据

长面板 CSV，列至少包含：`date, symbol, factor, fwd_ret`。

可选多周期列以拟合衰减：`fwd_ret_1, fwd_ret_5, fwd_ret_10, fwd_ret_20`（命名 `fwd_ret_{n}`）。

CLI 可用 `--factor-col` / `--ret-col` 改列名；单周期时用 `--horizon-label`（默认 `H`）标注周期。

面板可由用户自备，或在别处用 Pandadata 等拼好后传入——本 skill **不含数据库适配器**（见 `references/source_boundary.md`）。

## 工作流

### 第 1 步：确认面板与周期
- 列名、日期范围、标的覆盖是否够用
- 若只有单列 `fwd_ret`：报告该周期 IC + 稳定性；无法估半衰期
- 若有 `fwd_ret_{n}`：算衰减曲线并拟合半衰期

### 第 2 步：跑诊断脚本
```bash
python scripts/ic_decay.py --csv <panel.csv> [--name FACTOR] [--out report/] [--window 60] [--nw-lag 5]
```
得到：
- **全样本**：均值 IC、标准差、ICIR（raw = mean/std；年化 = mean/std·√252）、命中率（IC>0）、Newey-West t（默认 lag=5）
- **滚动**：默认 60 交易日窗口的均值 IC 与年化 ICIR
- **衰减**：各 horizon 均值 IC；对正均值周期做 `IC(h)=A·exp(-h/τ)` 的 log-linear OLS，半衰期 = τ·ln(2)

方法细节见 `references/ic-methods.md`。

### 第 3 步：样本护栏
- IC 观测 **&lt; 60**：拒绝计算（`ValueError`）
- IC 观测 **&lt; 252**：允许但报告显著警告“样本偏少”

### 第 4 步：输出报告
指定 `--out` 时写三种格式：`ic_decay.txt`、`ic_decay.json`、`ic_decay.html`（自包含内联 SVG，暖纸色调，零 CDN）。`--no-html` 可跳过 HTML。

结构化中文结论须标注：数据窗口、IC 观测数、是事实还是推断。半衰期是对历史衰减形状的拟合，**不是**“还能用 N 天”的保证。

## 严谨性红线

- **披露样本量**：短样本下 ICIR / NW-t / 半衰期都极不稳定——报告必须显示 `n_ic`
- **重叠收益**：多周期 `fwd_ret_h` 常由同一价格滚动生成，会抬高自相关、扭曲衰减形态——须在结论中提示
- **防未来函数**：因子只能用截至当日可知信息；本脚本不做取数，由用户保证面板无前瞻
- **不输出指令**：强度标签（strong / moderate / weak_or_noise）是证据描述，不是交易信号
- **可证伪**：`scripts/validate.py` 用合成数据验证强/反/噪声因子、快慢衰减半衰期、IC 界内、样本护栏、HTML 自包含与 JSON 键

## 自检

```bash
python scripts/validate.py   # 9 项合成自检；通过后可生成 examples/data/demo_panel.csv
```

## 边界与来源

数据来源边界见 `references/source_boundary.md`。方法说明见 `references/ic-methods.md`。本 skill 为 QuantSkills 社区原创；IC / ICIR / Newey-West / 半衰期为量化通用做法。与 `skill-factor-mine`（挖掘工作流）、季节性 / 同业对标等分析类 skill 互补，角度不重叠。

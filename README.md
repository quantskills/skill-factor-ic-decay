# skill-factor-ic-decay

**简体中文** | [English](README.en.md)

因子 IC 衰减与稳定性诊断。用日度截面 Spearman IC、ICIR、Newey-West 显著性、滚动稳定性与多周期半衰期，回答「预测力衰减有多快、IC 稳不稳、半衰期大概多久」。仅输出统计事实与推断，不提供买卖指令。

<p align="center">
  <img alt="role" src="https://img.shields.io/badge/role-IC衰减诊断-brightgreen">
  <img alt="output" src="https://img.shields.io/badge/output-IC·ICIR·半衰期·HTML-blue">
  <img alt="validation" src="https://img.shields.io/badge/validation-9%2F9自检通过-orange">
  <img alt="data" src="https://img.shields.io/badge/data-用户提供面板-9cf">
  <img alt="license" src="https://img.shields.io/badge/license-GPLv3-blue">
</p>

`skill-factor-ic-decay` 是 QuantSkills 社区的因子研究分析 Skill。它不挖因子、不做组合回测、不做季节性或同业对标——只诊断**截面预测力随时间与预测周期的衰减形态**。

## 这个 Skill 解决什么问题

"这个因子还能用多久？""IC 是不是在变弱？""半衰期大概几天？"——多数回答要么拍脑袋，要么只给一个全样本均值 IC，看不出衰减与稳定性。

本 skill 将其转化为可计算、可检验的诊断：

- **全样本**：均值 IC、ICIR（raw / 年化）、命中率、Newey-West t
- **滚动**：默认 60 日窗口的均值 IC 与年化 ICIR，看稳不稳
- **衰减**：多周期 `fwd_ret_{n}` 上的 IC 曲线 + 指数衰减半衰期

## 统计严谨性

- **披露样本量**：IC 观测 &lt;60 拒绝；&lt;252 警告样本偏少
- **显著性**：均值 IC 用 Newey-West t（默认 lag=5），处理序列自相关
- **重叠收益陷阱**：多周期前瞻收益常重叠，衰减解释须谨慎——写入每份报告
- **可证伪**：`scripts/validate.py` 验证强/反/噪声因子、快慢衰减、IC∈[-1,1]、样本护栏、HTML 自包含、JSON 键完备

## 快速开始

```bash
pip install -r requirements.txt

# 自检（9 项；若缺 demo 会写出 examples/data/demo_panel.csv）
python scripts/validate.py

# 示例面板
python scripts/ic_decay.py --csv examples/data/demo_panel.csv --name DEMO --out examples/output/

# 你自己的长面板（列：date,symbol,factor,fwd_ret；可选 fwd_ret_1/5/10/20）
python scripts/ic_decay.py --csv your_panel.csv --name MOM20 --out report/
```

指定 `--out` 时输出：`ic_decay.txt`、`ic_decay.json`、`ic_decay.html`（自包含内联 SVG，暖纸色调，离线可用）。加 `--no-html` 可跳过 HTML。

## 数据从哪来

框架中立，**用户提供面板**：
- 自备回测导出 / 研究库导出，整理成 `date,symbol,factor,fwd_ret`
- 可选在别处用 Pandadata 等拼面板后传入——本 skill 不含 DB 适配器

## 目录结构

```
skill-factor-ic-decay/
├── SKILL.md
├── README.md / README.en.md
├── agents/
│   ├── openai.yaml
│   ├── cursor-rule.mdc
│   └── portable-loader.md
├── scripts/
│   ├── ic_decay.py
│   └── validate.py
├── references/
│   ├── ic-methods.md
│   └── source_boundary.md
└── examples/
    ├── data/demo_panel.csv
    └── output/                 # txt + json + html 示例
```

## 运行时入口

支持 Claude Code、Codex、Cursor、Hermes、OpenClaw。原生 Skill 运行时加载 `SKILL.md`；Cursor 用 `agents/cursor-rule.mdc`；Hermes/OpenClaw 可用 `agents/portable-loader.md`。所有入口回到同一份方法与脚本。

## 与社区其他 skill 的分工

- `skill-factor-mine`：因子挖掘工作流 SOP —— **怎么挖**
- **本 skill**：IC 衰减 / 半衰期 / 稳定性 —— **挖出来后预测力怎么退化**
- 季节性 / 同业对标 / 归因：不同分析角度，不重叠

## License

GPL-3.0。QuantSkills 社区原创；IC / ICIR / Newey-West / 半衰期为量化通用做法。

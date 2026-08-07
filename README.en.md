# skill-factor-ic-decay

[简体中文](README.md) | **English**

Factor IC decay and stability diagnostics. Daily cross-sectional Spearman IC, ICIR, Newey-West significance, rolling stability, and multi-horizon half-life — answering how fast predictive power decays, whether IC is stable, and what the half-life looks like. Evidence-first; no buy/sell signals.

<p align="center">
  <img alt="role" src="https://img.shields.io/badge/role-IC%20decay%20diagnostics-brightgreen">
  <img alt="output" src="https://img.shields.io/badge/output-IC%20%C2%B7%20ICIR%20%C2%B7%20half--life%20%C2%B7%20HTML-blue">
  <img alt="validation" src="https://img.shields.io/badge/validation-9%2F9%20self--tests-orange">
  <img alt="data" src="https://img.shields.io/badge/data-user--supplied%20panel-9cf">
  <img alt="license" src="https://img.shields.io/badge/license-GPLv3-blue">
</p>

`skill-factor-ic-decay` is a QuantSkills analyst skill. It does not mine factors, backtest portfolios, or do seasonality / peer benchmarking — it only diagnoses **how cross-sectional predictive power decays over time and across horizons**.

## What it solves

"How long will this factor keep working?" "Is IC weakening?" "What's the half-life?" Most answers are either hand-wavy or a single full-sample mean IC with no decay or stability view.

This skill makes it computable and testable:

- **Full sample**: mean IC, ICIR (raw / annualized), hit rate, Newey-West t
- **Rolling**: default 60-day mean IC and annualized ICIR for stability
- **Decay**: IC curve on `fwd_ret_{n}` columns + exponential half-life fit

## Statistical rigor

- **Sample disclosure**: refuse if IC obs &lt; 60; warn if &lt; 252
- **Significance**: Newey-West t on the IC series (default lag=5)
- **Overlapping returns**: multi-horizon forwards often overlap — flagged in every report
- **Falsifiable**: `scripts/validate.py` checks strong/anti/noise factors, fast vs slow decay, IC∈[-1,1], sample guards, self-contained HTML, JSON keys

## Quick start

```bash
pip install -r requirements.txt
python scripts/validate.py
python scripts/ic_decay.py --csv examples/data/demo_panel.csv --name DEMO --out examples/output/
python scripts/ic_decay.py --csv your_panel.csv --name MOM20 --out report/
```

With `--out`: `ic_decay.txt`, `ic_decay.json`, `ic_decay.html` (self-contained inline SVG, warm paper tones, offline). Use `--no-html` to skip HTML.

## Data

Framework-neutral: **you supply the panel** (`date,symbol,factor,fwd_ret`; optional `fwd_ret_1/5/10/20`). Pandadata may be used elsewhere to build the panel — this skill has no DB adapters.

## Runtime entrypoints

Claude Code / Codex / native skill runtimes load `SKILL.md`; Cursor uses `agents/cursor-rule.mdc`; Hermes/OpenClaw can use `agents/portable-loader.md`. All converge on the same methods and scripts.

## How it fits

- `skill-factor-mine`: mining workflow — **how to dig**
- **this skill**: IC decay / half-life / stability — **how predictive power fades**
- Seasonality / peer benchmark / attribution: different angles, no overlap

## License

GPL-3.0. Original QuantSkills community work; IC / ICIR / Newey-West / half-life are standard quant practice.

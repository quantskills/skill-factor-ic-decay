"""因子 IC 衰减与稳定性诊断。

框架中立：输入长面板 [date, symbol, factor, fwd_ret]，输出日度截面 Spearman IC、
ICIR、Newey-West 显著性、滚动稳定性、多周期衰减曲线与半衰期。
事实优先，不输出买卖指令。

用法：
    python ic_decay.py --csv panel.csv
    python ic_decay.py --csv panel.csv --name MOM20 --out report/ --window 60
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MIN_IC_OBS = 60          # 少于此数拒绝计算
WARN_IC_OBS = 252        # 少于此数警告样本偏少
ANNUALIZE = 252.0        # 日度 IC 年化因子


# 自包含 HTML：内联 SVG + CSS + JS，零外部依赖；暖纸色调（非紫色）。
_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    --ground:#f6f3ec; --surface:#fffdf8; --surface-2:#f0ebe0;
    --ink:#23201a; --ink-2:#6b655a; --ink-3:#9a9284;
    --hair:rgba(35,32,26,.12); --hair-strong:rgba(35,32,26,.26);
    --up:#c0392b; --down:#147d6f; --accent:#a9791f;
    --accent-soft:rgba(169,121,31,.12); --faded:0.30;
    --shadow:0 1px 2px rgba(35,32,26,.06),0 6px 20px rgba(35,32,26,.05);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ground:#17150f; --surface:#201d16; --surface-2:#2a261d;
      --ink:#ece7db; --ink-2:#a9a293; --ink-3:#746d5e;
      --hair:rgba(236,231,219,.12); --hair-strong:rgba(236,231,219,.24);
      --up:#e15b4c; --down:#2aa697; --accent:#d6a94a;
      --accent-soft:rgba(214,169,74,.14);
      --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 22px rgba(0,0,0,.35);
    }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--ground); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",
      "Segoe UI","Noto Sans CJK SC",system-ui,sans-serif;
    line-height:1.6; font-variant-numeric:tabular-nums; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:920px; margin:0 auto; padding:40px 24px 64px; }
  .eyebrow { font-size:12px; letter-spacing:.18em; text-transform:uppercase;
    color:var(--accent); font-weight:600; margin:0 0 8px; }
  h1 { font-size:clamp(24px,4vw,32px); font-weight:700; margin:0 0 6px;
    letter-spacing:-.01em; text-wrap:balance; }
  .meta { color:var(--ink-2); font-size:14px; margin:0; }
  .meta b { color:var(--ink); font-weight:600; }
  .warn { margin:16px 0 0; padding:10px 14px; border-radius:10px; font-size:13px;
    background:rgba(192,57,43,.10); border:1px solid rgba(192,57,43,.30); color:var(--up); }
  .callout { margin:24px 0 32px; padding:18px 20px; border-radius:12px;
    background:var(--accent-soft); border:1px solid var(--hair);
    display:flex; flex-wrap:wrap; gap:6px 28px; align-items:baseline; }
  .callout .lead { font-weight:600; font-size:14px; color:var(--accent);
    letter-spacing:.02em; width:100%; margin-bottom:2px; }
  .callout .stat { font-size:14px; color:var(--ink-2); }
  .callout .stat b { color:var(--ink); font-weight:700; font-size:16px; }
  section { margin-top:40px; }
  .sec-head { display:flex; align-items:baseline; justify-content:space-between;
    gap:12px; margin-bottom:6px; flex-wrap:wrap; }
  h2 { font-size:17px; font-weight:700; margin:0; letter-spacing:-.005em; }
  .sec-note { font-size:13px; color:var(--ink-3); margin:0; }
  .card { background:var(--surface); border:1px solid var(--hair); border-radius:14px;
    box-shadow:var(--shadow); padding:20px 20px 12px; margin-top:14px; }
  .chart-scroll { overflow-x:auto; }
  svg { display:block; width:100%; min-width:520px; height:auto; }
  .tbl-scroll { overflow-x:auto; margin-top:14px; }
  table { border-collapse:collapse; width:100%; min-width:480px; font-size:13px; }
  th,td { padding:8px 10px; text-align:right; white-space:nowrap; }
  th { color:var(--ink-3); font-weight:600; font-size:12px; letter-spacing:.03em;
    border-bottom:1px solid var(--hair-strong); }
  td { border-bottom:1px solid var(--hair); color:var(--ink-2); }
  th:first-child,td:first-child { text-align:left; }
  td.up { color:var(--up); } td.down { color:var(--down); }
  .caveats { margin-top:16px; padding:18px 20px; border-radius:12px;
    background:var(--surface-2); border:1px solid var(--hair); }
  .caveats h3 { margin:0 0 10px; font-size:13px; letter-spacing:.04em; text-transform:uppercase;
    color:var(--ink-3); font-weight:700; }
  .caveats ul { margin:0; padding-left:18px; }
  .caveats li { font-size:13px; color:var(--ink-2); margin-bottom:6px; }
  footer { margin-top:40px; padding-top:16px; border-top:1px solid var(--hair);
    font-size:12px; color:var(--ink-3); display:flex; justify-content:space-between;
    flex-wrap:wrap; gap:8px; }
  @media (max-width:560px) { .wrap { padding:28px 16px 48px; } .callout { gap:4px 18px; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">因子 IC 衰减诊断</p>
    <h1>__NAME__ · IC Decay &amp; Stability</h1>
    <p class="meta">__META__</p>
    __WARN__
  </header>
  __CALLOUT__
  <section>
    <div class="sec-head">
      <h2>滚动 IC</h2>
      <p class="sec-note">窗口 __WINDOW__ 交易日 · 日度截面 Spearman</p>
    </div>
    <div class="card">
      <div class="chart-scroll">
        <svg id="roll" viewBox="0 0 760 280" role="img" aria-label="滚动IC折线图"></svg>
      </div>
    </div>
  </section>
  <section>
    <div class="sec-head">
      <h2>IC 衰减曲线</h2>
      <p class="sec-note">多周期均值 IC · 指数衰减拟合（若可）</p>
    </div>
    <div class="card">
      <div class="chart-scroll">
        <svg id="decay" viewBox="0 0 760 280" role="img" aria-label="IC衰减曲线"></svg>
      </div>
      <div class="tbl-scroll">
        <table id="dtbl">
          <thead><tr><th>周期</th><th>均值 IC</th><th>IC 标准差</th><th>观测数</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>
  <div class="caveats">
    <h3>严谨性说明</h3>
    <ul>__CAVEATS__</ul>
  </div>
  <footer>
    <span>由 skill-factor-ic-decay 生成</span>
    <span>事实优先 · 不输出买卖指令</span>
  </footer>
</div>
<script>
  const ROLL = __ROLL_JSON__;
  const DECAY = __DECAY_JSON__;
  const FIT = __FIT_JSON__;
  const SVGNS = "http://www.w3.org/2000/svg";
  const el = (n, a={}) => { const e = document.createElementNS(SVGNS, n);
    for (const k in a) e.setAttribute(k, a[k]); return e; };
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const fmt = (x, dp=4) => (x == null || isNaN(x)) ? "—" : Number(x).toFixed(dp);

  function lineChart(svgId, pts, yKey, label) {
    const svg = document.getElementById(svgId); svg.textContent = "";
    const W=760,H=280,padL=52,padR=16,padT=20,padB=36;
    const plotW=W-padL-padR, plotH=H-padT-padB;
    const ys = pts.map(p => p[yKey]).filter(v => v != null && !isNaN(v));
    if (!ys.length) {
      const t=el("text",{x:W/2,y:H/2,"text-anchor":"middle","font-size":14,fill:css("--ink-3")});
      t.textContent="无数据"; svg.appendChild(t); return;
    }
    const ymin = Math.min(...ys, 0), ymax = Math.max(...ys, 0);
    const pad = Math.max((ymax - ymin) * 0.12, 0.01);
    const y0 = ymin - pad, y1 = ymax + pad;
    const xOf = i => padL + (pts.length <= 1 ? plotW/2 : i / (pts.length - 1) * plotW);
    const yOf = v => padT + (1 - (v - y0) / (y1 - y0)) * plotH;
    const ink3=css("--ink-3"), hair=css("--hair"), hairS=css("--hair-strong"),
          accent=css("--accent"), up=css("--up"), down=css("--down");
    [0, (y0+y1)/2, y1, y0].forEach(v => {
      const y=yOf(v);
      svg.appendChild(el("line",{x1:padL,y1:y,x2:W-padR,y2:y,
        stroke:Math.abs(v)<1e-12?hairS:hair,"stroke-width":Math.abs(v)<1e-12?1.3:1,
        "stroke-dasharray":Math.abs(v)<1e-12?"0":"3 4"}));
      const t=el("text",{x:padL-8,y:y+4,"text-anchor":"end","font-size":11,fill:ink3});
      t.textContent=fmt(v,3); svg.appendChild(t);
    });
    let d="";
    pts.forEach((p,i) => {
      const v=p[yKey]; if (v==null||isNaN(v)) return;
      d += (d?" L":"M")+xOf(i)+","+yOf(v);
    });
    if (d) svg.appendChild(el("path",{d,fill:"none",stroke:accent,"stroke-width":2}));
    // zero line already drawn; end labels
    if (pts.length) {
      const t0=el("text",{x:padL,y:H-10,"font-size":11,fill:ink3}); t0.textContent=pts[0].date||""; svg.appendChild(t0);
      const t1=el("text",{x:W-padR,y:H-10,"text-anchor":"end","font-size":11,fill:ink3});
      t1.textContent=pts[pts.length-1].date||""; svg.appendChild(t1);
    }
    const lab=el("text",{x:padL+4,y:padT+12,"font-size":12,fill:ink3}); lab.textContent=label; svg.appendChild(lab);
  }

  function decayChart() {
    const svg = document.getElementById("decay"); svg.textContent = "";
    const W=760,H=280,padL=52,padR=16,padT=20,padB=40;
    const plotW=W-padL-padR, plotH=H-padT-padB;
    if (!DECAY.length) {
      const t=el("text",{x:W/2,y:H/2,"text-anchor":"middle","font-size":14,fill:css("--ink-3")});
      t.textContent="单周期模式（无多周期衰减曲线）"; svg.appendChild(t); return;
    }
    const hs = DECAY.map(d => d.h);
    const ics = DECAY.map(d => d.mean_ic);
    const hmin=Math.min(...hs), hmax=Math.max(...hs);
    const ymin=Math.min(...ics,0), ymax=Math.max(...ics,0);
    const pad=Math.max((ymax-ymin)*0.15, 0.005);
    const y0=ymin-pad, y1=ymax+pad;
    const xOf = h => padL + ((h - hmin) / Math.max(hmax - hmin, 1)) * plotW;
    const yOf = v => padT + (1 - (v - y0) / (y1 - y0)) * plotH;
    const ink3=css("--ink-3"), hair=css("--hair"), hairS=css("--hair-strong"),
          accent=css("--accent"), up=css("--up");
    [0].forEach(v => {
      const y=yOf(v);
      svg.appendChild(el("line",{x1:padL,y1:y,x2:W-padR,y2:y,stroke:hairS,"stroke-width":1.3}));
    });
    // fitted curve
    if (FIT && FIT.A != null && FIT.tau != null && FIT.tau > 0) {
      let d="";
      for (let i=0;i<=40;i++) {
        const h = hmin + (hmax-hmin)*i/40;
        const v = FIT.A * Math.exp(-h / FIT.tau);
        d += (i?" L":"M")+xOf(h)+","+yOf(v);
      }
      svg.appendChild(el("path",{d,fill:"none",stroke:accent,"stroke-width":1.5,"stroke-dasharray":"5 4"}));
    }
    DECAY.forEach(p => {
      svg.appendChild(el("circle",{cx:xOf(p.h),cy:yOf(p.mean_ic),r:5,fill:p.mean_ic>=0?up:css("--down")}));
      const t=el("text",{x:xOf(p.h),y:H-14,"text-anchor":"middle","font-size":11,fill:ink3});
      t.textContent="H"+p.h; svg.appendChild(t);
    });
  }

  function decayTable() {
    const tb=document.querySelector("#dtbl tbody");
    DECAY.forEach(d => {
      const tr=document.createElement("tr");
      const cls=d.mean_ic>=0?"up":"down";
      tr.innerHTML=`<td>H${d.h}</td><td class="${cls}">${fmt(d.mean_ic)}</td>`+
        `<td>${fmt(d.std_ic)}</td><td>${d.n}</td>`;
      tb.appendChild(tr);
    });
  }

  // downsample rolling for SVG readability
  const step = Math.max(1, Math.floor(ROLL.length / 180));
  const rollPts = ROLL.filter((_,i)=>i%step===0).map(r=>({date:r.date, ic:r.mean_ic}));
  lineChart("roll", rollPts, "ic", "rolling mean IC");
  decayChart(); decayTable();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    lineChart("roll", rollPts, "ic", "rolling mean IC"); decayChart();
  });
</script>
</body>
</html>
"""


def load_panel(
    path: str,
    factor_col: str = "factor",
    ret_col: str = "fwd_ret",
) -> pd.DataFrame:
    """加载长面板 CSV。保留所有 fwd_ret_{n} 列以便衰减曲线。"""
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}

    def _pick(*names):
        for n in names:
            if n.lower() in cols:
                return cols[n.lower()]
        return None

    dcol = _pick("date", "日期", "trade_date")
    scol = _pick("symbol", "code", "ticker", "股票代码", "证券代码")
    fcol = _pick(factor_col, "factor", "signal", "alpha", "因子")
    if not dcol or not scol or not fcol:
        raise ValueError(
            f"CSV 需含 date/symbol/{factor_col} 列，实际列：{list(df.columns)}"
        )

    out = pd.DataFrame({
        "date": pd.to_datetime(df[dcol]),
        "symbol": df[scol].astype(str),
        "factor": pd.to_numeric(df[fcol], errors="coerce"),
    })

    # 主收益列
    rcol = _pick(ret_col, "fwd_ret", "forward_return", "ret", "收益")
    if rcol:
        out["fwd_ret"] = pd.to_numeric(df[rcol], errors="coerce")

    # 多周期列 fwd_ret_{n}
    for c in df.columns:
        m = re.match(r"(?i)^fwd_ret_(\d+)$", str(c).strip())
        if m:
            out[f"fwd_ret_{int(m.group(1))}"] = pd.to_numeric(df[c], errors="coerce")

    if "fwd_ret" not in out.columns:
        # 若只有 fwd_ret_n，用最短周期作主列
        multi = sorted(
            [int(re.match(r"fwd_ret_(\d+)$", c).group(1))
             for c in out.columns if re.match(r"fwd_ret_\d+$", c)]
        )
        if multi:
            out["fwd_ret"] = out[f"fwd_ret_{multi[0]}"]
        else:
            raise ValueError(
                f"CSV 需含 {ret_col} 或 fwd_ret_{{n}} 列，实际列：{list(df.columns)}"
            )

    out = out.dropna(subset=["date", "symbol", "factor"]).sort_values(
        ["date", "symbol"]
    ).reset_index(drop=True)
    return out


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """两向量 Spearman 秩相关；样本不足返回 nan。"""
    n = len(x)
    if n < 3:
        return float("nan")
    rx = pd.Series(x).rank(method="average").to_numpy()
    ry = pd.Series(y).rank(method="average").to_numpy()
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    den = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    if den <= 0:
        return float("nan")
    ic = float((rx * ry).sum() / den)
    # 数值护栏
    if ic > 1.0:
        ic = 1.0
    elif ic < -1.0:
        ic = -1.0
    return ic


def daily_ic(panel: pd.DataFrame, ret_col: str = "fwd_ret") -> pd.Series:
    """日度截面 Spearman IC：每个交易日对 symbol 截面算一次。"""
    if ret_col not in panel.columns:
        raise ValueError(f"面板缺少收益列 {ret_col}")

    rows = []
    for dt, g in panel.groupby("date", sort=True):
        sub = g[["factor", ret_col]].dropna()
        if len(sub) < 3:
            continue
        ic = _spearman(sub["factor"].to_numpy(float), sub[ret_col].to_numpy(float))
        if not np.isnan(ic):
            assert -1.0 - 1e-9 <= ic <= 1.0 + 1e-9, f"IC out of bounds: {ic}"
            rows.append((dt, ic))
    if not rows:
        return pd.Series(dtype=float, name="ic")
    s = pd.Series({d: v for d, v in rows}, name="ic").sort_index()
    s.index = pd.to_datetime(s.index)
    return s


def newey_west_t(x, lag: int = 5) -> float:
    """均值是否显著异于 0 的 Newey-West t 统计量（Bartlett 核）。"""
    arr = np.asarray(x, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n < max(lag + 2, 5):
        return float("nan")
    mean = float(arr.mean())
    u = arr - mean
    gamma0 = float(np.dot(u, u) / n)
    nw = gamma0
    L = int(lag)
    for j in range(1, L + 1):
        w = 1.0 - j / (L + 1.0)
        gamma_j = float(np.dot(u[j:], u[:-j]) / n)
        nw += 2.0 * w * gamma_j
    # 方差估计可为负（极端小样本），截断
    if nw <= 0:
        return float("nan")
    se = math.sqrt(nw / n)
    if se <= 0:
        return float("nan")
    return mean / se


def _ic_summary(ic: pd.Series, nw_lag: int = 5) -> dict:
    arr = ic.dropna().to_numpy(float)
    n = len(arr)
    if n == 0:
        return {
            "n": 0, "mean_ic": float("nan"), "std_ic": float("nan"),
            "icir_raw": float("nan"), "icir_ann": float("nan"),
            "hit_rate": float("nan"), "nw_t": float("nan"),
        }
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if n > 1 else float("nan")
    icir_raw = mean / std if std and std > 0 else float("nan")
    icir_ann = icir_raw * math.sqrt(ANNUALIZE) if not np.isnan(icir_raw) else float("nan")
    hit = float((arr > 0).mean())
    return {
        "n": n,
        "mean_ic": mean,
        "std_ic": std,
        "icir_raw": icir_raw,
        "icir_ann": icir_ann,
        "hit_rate": hit,
        "nw_t": float(newey_west_t(arr, lag=nw_lag)),
    }


def rolling_ic_stats(ic: pd.Series, window: int = 60) -> pd.DataFrame:
    """滚动窗口均值 IC 与年化 ICIR。"""
    s = ic.dropna().sort_index()
    if s.empty:
        return pd.DataFrame(columns=["date", "mean_ic", "std_ic", "icir_ann"])
    roll_mean = s.rolling(window, min_periods=max(10, window // 3)).mean()
    roll_std = s.rolling(window, min_periods=max(10, window // 3)).std(ddof=1)
    icir = roll_mean / roll_std * math.sqrt(ANNUALIZE)
    out = pd.DataFrame({
        "date": roll_mean.index,
        "mean_ic": roll_mean.to_numpy(),
        "std_ic": roll_std.to_numpy(),
        "icir_ann": icir.to_numpy(),
    }).dropna(subset=["mean_ic"]).reset_index(drop=True)
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def _detect_horizons(panel: pd.DataFrame) -> list[tuple[int | str, str]]:
    """返回 [(horizon_label, column_name), ...]。优先 fwd_ret_{n}。"""
    found = []
    for c in panel.columns:
        m = re.match(r"^fwd_ret_(\d+)$", c)
        if m:
            found.append((int(m.group(1)), c))
    if found:
        return sorted(found, key=lambda x: x[0])
    if "fwd_ret" in panel.columns:
        return [("H", "fwd_ret")]
    return []


def decay_curve(
    panel: pd.DataFrame,
    nw_lag: int = 5,
    horizon_label: str = "H",
) -> list[dict]:
    """各预测周期上的均值 IC 曲线。"""
    horizons = _detect_horizons(panel)
    if not horizons:
        return []
    # 单列模式：用自定义标签
    if len(horizons) == 1 and horizons[0][0] == "H":
        horizons = [(horizon_label, horizons[0][1])]

    curve = []
    for h, col in horizons:
        ic = daily_ic(panel, ret_col=col)
        sm = _ic_summary(ic, nw_lag=nw_lag)
        # 数值 h 用于拟合；字符串标签则尝试解析
        if isinstance(h, int):
            h_num = h
            h_lab = f"H{h}"
        else:
            m = re.search(r"(\d+)", str(h))
            h_num = int(m.group(1)) if m else None
            h_lab = str(h)
        curve.append({
            "horizon": h_lab,
            "h": h_num if h_num is not None else 0,
            "column": col,
            "mean_ic": sm["mean_ic"],
            "std_ic": sm["std_ic"],
            "n": sm["n"],
            "icir_ann": sm["icir_ann"],
            "nw_t": sm["nw_t"],
            "hit_rate": sm["hit_rate"],
        })
    return curve


def fit_half_life(curve: list[dict]) -> dict:
    """对正均值 IC 周期做 log-linear OLS：log(IC)=log(A)-h/τ，半衰期=τ*ln(2)。"""
    pts = [
        (float(p["h"]), float(p["mean_ic"]))
        for p in curve
        if p.get("h") is not None
        and p["h"] > 0
        and p.get("mean_ic") is not None
        and not np.isnan(p["mean_ic"])
        and p["mean_ic"] > 0
    ]
    empty = {
        "A": None, "tau": None, "half_life": None,
        "r_squared": None, "n_points": 0, "fitted": False,
        "note": "不足以拟合指数衰减（需 ≥2 个正均值 IC 周期）",
    }
    if len(pts) < 2:
        return empty

    hs = np.array([p[0] for p in pts], dtype=float)
    log_ic = np.log(np.array([p[1] for p in pts], dtype=float))
    # OLS: log_ic = a + b * h,  b = -1/τ,  A = exp(a)
    X = np.column_stack([np.ones(len(hs)), hs])
    try:
        beta, _, _, _ = np.linalg.lstsq(X, log_ic, rcond=None)
    except np.linalg.LinAlgError:
        return {**empty, "note": "OLS 拟合失败"}
    a, b = float(beta[0]), float(beta[1])
    if b >= 0:
        # 衰减应为负斜率；若不衰减或递增则不报告正半衰期
        return {
            "A": float(math.exp(a)),
            "tau": None,
            "half_life": None,
            "r_squared": None,
            "n_points": len(pts),
            "fitted": False,
            "note": "IC 未呈指数衰减（斜率≥0），半衰期未定义",
        }
    tau = -1.0 / b
    half_life = tau * math.log(2.0)
    assert half_life > 0, "half-life must be positive when fitted"
    yhat = a + b * hs
    ss_res = float(((log_ic - yhat) ** 2).sum())
    ss_tot = float(((log_ic - log_ic.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {
        "A": float(math.exp(a)),
        "tau": float(tau),
        "half_life": float(half_life),
        "r_squared": float(r2),
        "n_points": len(pts),
        "fitted": True,
        "note": f"IC(h)=A·exp(-h/τ)，τ={tau:.2f}，半衰期={half_life:.2f} 日",
    }


def build_report(
    panel: pd.DataFrame,
    name: str | None = None,
    window: int = 60,
    nw_lag: int = 5,
    horizon_label: str = "H",
) -> dict:
    """组装完整诊断报告（可序列化为 JSON）。"""
    ic = daily_ic(panel, ret_col="fwd_ret")
    n = int(ic.dropna().shape[0])
    if n < MIN_IC_OBS:
        raise ValueError(
            f"IC 观测数过少（{n} < {MIN_IC_OBS}），拒绝输出不可靠诊断。"
            "请提供更长的面板（建议 ≥252 个交易日）。"
        )
    low_sample = n < WARN_IC_OBS
    summary = _ic_summary(ic, nw_lag=nw_lag)
    rolling = rolling_ic_stats(ic, window=window)
    curve = decay_curve(panel, nw_lag=nw_lag, horizon_label=horizon_label)
    fit = fit_half_life(curve) if len(curve) >= 2 else {
        "A": None, "tau": None, "half_life": None,
        "r_squared": None, "n_points": 0, "fitted": False,
        "note": "单周期模式，无法估计半衰期；提供 fwd_ret_1/5/10/20 等列可拟合",
    }

    # 强度标签（证据描述，非交易指令）
    mean_ic = summary["mean_ic"]
    nw_t = summary["nw_t"]
    if abs(mean_ic) >= 0.03 and abs(nw_t) >= 2.0:
        strength = "strong"
    elif abs(mean_ic) >= 0.01 and abs(nw_t) >= 1.5:
        strength = "moderate"
    else:
        strength = "weak_or_noise"

    dates = panel["date"]
    caveats = [
        "IC 是历史截面预测力的统计描述，不是买卖指令；衰减快不代表立刻失效，慢也不保证持续有效。",
        f"日度 IC 观测数 n={n}" + ("，少于一年（252），样本偏少，谨慎解读。" if low_sample else "。"),
        f"Newey-West t 使用 lag={nw_lag}（处理 IC 序列自相关）；重叠收益周期会进一步抬高自相关。",
        "多周期 fwd_ret_h 若由同一价格序列滚动生成，存在重叠持有期，衰减曲线解释需谨慎。",
        "防未来函数：因子只能使用截至当日可知信息；本脚本不做取数，由用户保证面板无前瞻。",
        "本结果不构成投资建议。",
    ]

    return {
        "name": name or "factor",
        "n_ic": n,
        "date_start": str(pd.to_datetime(dates.min()).date()),
        "date_end": str(pd.to_datetime(dates.max()).date()),
        "n_symbols": int(panel["symbol"].nunique()),
        "low_sample_warning": low_sample,
        "window": window,
        "nw_lag": nw_lag,
        "summary": summary,
        "strength": strength,
        "rolling": rolling.to_dict(orient="records"),
        "decay_curve": curve,
        "half_life_fit": fit,
        "caveats": caveats,
    }


def render_text(rep: dict) -> str:
    L = []
    L.append(f"因子 IC 衰减诊断（{rep['name']}）")
    L.append("=" * 56)
    L.append(
        f"窗口：{rep['date_start']} → {rep['date_end']}  ·  "
        f"标的数 {rep['n_symbols']}  ·  IC 观测 {rep['n_ic']}"
        + ("  ⚠ 样本偏少" if rep["low_sample_warning"] else "")
    )
    s = rep["summary"]
    L.append("")
    L.append("【全样本 IC】")
    L.append(f"  均值 IC     : {s['mean_ic']:+.4f}")
    L.append(f"  标准差      : {s['std_ic']:.4f}")
    L.append(f"  ICIR (raw)  : {s['icir_raw']:+.3f}   (= mean/std)")
    L.append(f"  ICIR (年化) : {s['icir_ann']:+.3f}   (= mean/std * sqrt(252))")
    L.append(f"  命中率 IC>0 : {s['hit_rate']:.1%}")
    L.append(f"  Newey-West t: {s['nw_t']:+.2f}  (lag={rep['nw_lag']})")
    L.append(f"  强度标签    : {rep['strength']}  （证据描述，非交易信号）")
    L.append("")
    L.append(f"【滚动 IC】窗口={rep['window']} 交易日")
    roll = rep["rolling"]
    if roll:
        last = roll[-1]
        L.append(
            f"  最新滚动均值 IC={last['mean_ic']:+.4f}，"
            f"年化 ICIR={last.get('icir_ann', float('nan')):+.3f}  "
            f"（截至 {last['date']}）"
        )
        means = [r["mean_ic"] for r in roll if r.get("mean_ic") is not None]
        if means:
            L.append(
                f"  滚动均值 IC 范围：[{min(means):+.4f}, {max(means):+.4f}]"
            )
    else:
        L.append("  （滚动序列为空）")

    L.append("")
    L.append("【衰减曲线】")
    curve = rep["decay_curve"]
    if curve:
        L.append(f"  {'周期':>6} {'均值IC':>10} {'标准差':>10} {'ICIR年化':>10} {'NW-t':>8} {'n':>6}")
        for p in curve:
            L.append(
                f"  {str(p['horizon']):>6} {p['mean_ic']:>+10.4f} "
                f"{p['std_ic']:>10.4f} {p['icir_ann']:>+10.3f} "
                f"{p['nw_t']:>+8.2f} {p['n']:>6}"
            )
    else:
        L.append("  （无衰减曲线）")

    fit = rep["half_life_fit"]
    L.append("")
    L.append("【半衰期拟合】")
    if fit.get("fitted"):
        L.append(f"  A={fit['A']:.4f}，τ={fit['tau']:.2f}，半衰期={fit['half_life']:.2f} 日")
        L.append(f"  R²={fit['r_squared']:.3f}，拟合点数={fit['n_points']}")
    else:
        L.append(f"  未拟合：{fit.get('note', '')}")

    L.append("")
    L.append("说明：")
    for c in rep["caveats"]:
        L.append(f"  - {c}")
    return "\n".join(L)


def _html_escape(s) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
    )


def _json_safe(obj):
    """将 nan/inf 转为 None，便于 JSON。"""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def render_html(rep: dict) -> str:
    """自包含 HTML 报告（暖纸色调，内联 SVG，无 CDN）。"""
    name = rep.get("name") or "factor"
    s = rep["summary"]
    fit = rep["half_life_fit"]

    meta = (
        f"窗口 <b>{_html_escape(rep['date_start'])}</b> → "
        f"<b>{_html_escape(rep['date_end'])}</b> &nbsp;·&nbsp; "
        f"IC 观测 <b>{rep['n_ic']}</b> &nbsp;·&nbsp; "
        f"标的 <b>{rep['n_symbols']}</b>"
    )
    warn = ""
    if rep.get("low_sample_warning"):
        warn = (
            '<div class="warn">⚠ IC 观测少于 252 个交易日，样本偏少，'
            "衰减与稳定性结论请谨慎解读。</div>"
        )

    hl = fit.get("half_life")
    hl_txt = f"{hl:.1f} 日" if hl is not None else "—"
    callout = (
        '<div class="callout">'
        '<div class="lead">核心指标</div>'
        f'<span class="stat">均值 IC <b>{s["mean_ic"]:+.4f}</b></span>'
        f'<span class="stat">年化 ICIR <b>{s["icir_ann"]:+.2f}</b></span>'
        f'<span class="stat">NW-t <b>{s["nw_t"]:+.2f}</b></span>'
        f'<span class="stat">命中率 <b>{s["hit_rate"]:.0%}</b></span>'
        f'<span class="stat">半衰期 <b>{_html_escape(hl_txt)}</b></span>'
        f'<span class="stat">强度 <b>{_html_escape(rep["strength"])}</b></span>'
        "</div>"
    )

    caveats = "".join(f"<li>{_html_escape(c)}</li>" for c in rep["caveats"])

    # 下采样滚动点进 HTML，控制体积
    roll = rep.get("rolling") or []
    step = max(1, len(roll) // 400) if roll else 1
    roll_slim = [
        {"date": r["date"], "mean_ic": r["mean_ic"]}
        for i, r in enumerate(roll) if i % step == 0
    ]
    decay = [
        {
            "h": p.get("h"),
            "horizon": p.get("horizon"),
            "mean_ic": p.get("mean_ic"),
            "std_ic": p.get("std_ic"),
            "n": p.get("n"),
        }
        for p in (rep.get("decay_curve") or [])
    ]
    fit_js = {
        "A": fit.get("A"),
        "tau": fit.get("tau"),
        "half_life": fit.get("half_life"),
    }

    html = _HTML_TEMPLATE
    html = html.replace("__TITLE__", _html_escape(f"IC Decay · {name}"))
    html = html.replace("__NAME__", _html_escape(name))
    html = html.replace("__META__", meta)
    html = html.replace("__WARN__", warn)
    html = html.replace("__CALLOUT__", callout)
    html = html.replace("__CAVEATS__", caveats)
    html = html.replace("__WINDOW__", str(rep.get("window", 60)))
    html = html.replace("__ROLL_JSON__", json.dumps(_json_safe(roll_slim), ensure_ascii=False))
    html = html.replace("__DECAY_JSON__", json.dumps(_json_safe(decay), ensure_ascii=False))
    html = html.replace("__FIT_JSON__", json.dumps(_json_safe(fit_js), ensure_ascii=False))
    return html


def _safe_print(text: str) -> None:
    """Windows GBK 控制台下避免 UnicodeEncodeError。"""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="因子 IC 衰减与稳定性诊断")
    p.add_argument("--csv", required=True, help="长面板 CSV：date,symbol,factor,fwd_ret")
    p.add_argument("--name", default=None, help="因子名称")
    p.add_argument("--out", default=None, help="输出目录（写 txt/json/html）")
    p.add_argument("--window", type=int, default=60, help="滚动窗口（交易日）")
    p.add_argument("--nw-lag", type=int, default=5, help="Newey-West lag")
    p.add_argument("--factor-col", default="factor")
    p.add_argument("--ret-col", default="fwd_ret")
    p.add_argument("--horizon-label", default="H", help="单周期模式下的周期标签")
    p.add_argument("--no-html", action="store_true", help="跳过 HTML 输出")
    args = p.parse_args(argv)

    panel = load_panel(args.csv, factor_col=args.factor_col, ret_col=args.ret_col)
    rep = build_report(
        panel,
        name=args.name,
        window=args.window,
        nw_lag=args.nw_lag,
        horizon_label=args.horizon_label,
    )
    text = render_text(rep)
    _safe_print(text)

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "ic_decay.txt").write_text(text, encoding="utf-8")
        (out / "ic_decay.json").write_text(
            json.dumps(_json_safe(rep), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if not args.no_html:
            (out / "ic_decay.html").write_text(render_html(rep), encoding="utf-8")
        _safe_print(
            f"\n已写入 {out}/ic_decay.{{txt,json"
            + ("" if args.no_html else ",html")
            + "}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

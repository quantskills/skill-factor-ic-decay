"""IC 衰减诊断自检：构造已知 IC 强弱与快慢衰减的合成面板，验证算法。

全部通过退出码 0，否则 1。若 examples/data/demo_panel.csv 缺失则顺带写出。
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

# 同目录导入
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ic_decay import (  # noqa: E402
    MIN_IC_OBS,
    build_report,
    daily_ic,
    decay_curve,
    fit_half_life,
    load_panel,
    render_html,
    _json_safe,
)

RNG = np.random.default_rng(20260807)
ROOT = Path(__file__).resolve().parents[1]
DEMO_CSV = ROOT / "examples" / "data" / "demo_panel.csv"


def _make_panel(
    n_days: int = 320,
    n_symbols: int = 40,
    mode: str = "strong",
    horizons: tuple[int, ...] | None = (1, 5, 10, 20),
    decay_tau: float | None = None,
    noise: float = 0.5,
    start: str = "2020-01-02",
) -> pd.DataFrame:
    """合成长面板。

    mode:
      strong     — factor ≈ future ret + noise → 正 IC
      anti       — factor ≈ -future ret → 负 IC
      noise      — 纯噪声因子
      fast_decay — 短周期强、长周期弱（小 τ）
      slow_decay — 衰减更慢（大 τ）
    """
    dates = pd.bdate_range(start, periods=n_days)
    symbols = [f"S{i:03d}" for i in range(n_symbols)]
    # 每标的潜在收益驱动
    true_alpha = RNG.normal(0, 1.0, size=(n_days, n_symbols))
    idio = RNG.normal(0, 1.0, size=(n_days, n_symbols))

    if horizons is None:
        horizons = ()

    rows = []
    for ti, dt in enumerate(dates):
        for si, sym in enumerate(symbols):
            # 用当期 true_alpha 作为"可知信息"；前瞻收益由衰减核生成
            base = true_alpha[ti, si]
            row = {
                "date": dt,
                "symbol": sym,
                "factor": np.nan,  # 稍后填
            }
            # 单周期 fwd_ret：默认 H=1 风格
            if mode in ("strong", "anti", "noise"):
                fwd = base + noise * idio[ti, si]
                row["fwd_ret"] = fwd
                if mode == "strong":
                    row["factor"] = base + 0.15 * RNG.normal()
                elif mode == "anti":
                    row["factor"] = -base + 0.15 * RNG.normal()
                else:
                    row["factor"] = RNG.normal()
            else:
                # 多周期衰减：IC(h) ∝ exp(-h/τ)
                tau = decay_tau if decay_tau is not None else (4.0 if mode == "fast_decay" else 25.0)
                row["factor"] = base + 0.05 * RNG.normal()
                for h in horizons:
                    # 前瞻收益 = 衰减后的可预测部分 + 噪声
                    # 可预测强度随 h 指数衰减，使截面 IC 近似随 h 衰减
                    strength = math_exp_neg(h, tau)
                    row[f"fwd_ret_{h}"] = strength * base + noise * RNG.normal()
                # 主列用最短周期
                h0 = min(horizons) if horizons else 1
                row["fwd_ret"] = row.get(f"fwd_ret_{h0}", base)
            rows.append(row)
    return pd.DataFrame(rows)


def math_exp_neg(h: float, tau: float) -> float:
    return float(np.exp(-float(h) / float(tau)))


def ensure_demo_panel() -> Path:
    """写出 demo 面板（快衰减合成，含多周期）。"""
    DEMO_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not DEMO_CSV.exists():
        df = _make_panel(
            n_days=400, n_symbols=50, mode="fast_decay",
            horizons=(1, 5, 10, 20), decay_tau=6.0, noise=0.35,
        )
        df.to_csv(DEMO_CSV, index=False)
    return DEMO_CSV


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_strong_factor_positive_ic():
    df = _make_panel(n_days=300, mode="strong", horizons=None, noise=0.3)
    rep = build_report(df, name="strong")
    assert rep["summary"]["mean_ic"] > 0.15, rep["summary"]["mean_ic"]
    assert rep["summary"]["nw_t"] > 2.0, rep["summary"]["nw_t"]
    assert rep["strength"] in ("strong", "moderate")


def test_anti_factor_negative_ic():
    df = _make_panel(n_days=300, mode="anti", horizons=None, noise=0.3)
    rep = build_report(df, name="anti")
    assert rep["summary"]["mean_ic"] < -0.15, rep["summary"]["mean_ic"]
    assert rep["summary"]["nw_t"] < -2.0, rep["summary"]["nw_t"]


def test_noise_factor_not_strong():
    df = _make_panel(n_days=300, mode="noise", horizons=None, noise=1.0)
    rep = build_report(df, name="noise")
    assert abs(rep["summary"]["mean_ic"]) < 0.08, rep["summary"]["mean_ic"]
    # 纯噪声不得标 strong；偶发 |NW-t| 略高可落在 moderate，但不算有效因子
    assert rep["strength"] != "strong", rep["strength"]


def test_fast_decay_short_half_life():
    df = _make_panel(
        n_days=350, n_symbols=50, mode="fast_decay",
        horizons=(1, 5, 10, 20), decay_tau=5.0, noise=0.25,
    )
    curve = decay_curve(df)
    fit = fit_half_life(curve)
    assert fit["fitted"], fit
    assert fit["half_life"] is not None and fit["half_life"] > 0
    assert fit["half_life"] < 15.0, f"fast half-life too large: {fit['half_life']}"
    # h=1 显著强于 h=20
    by_h = {p["h"]: p["mean_ic"] for p in curve}
    assert by_h[1] > by_h[20] + 0.05, by_h


def test_slow_decay_longer_half_life():
    fast = _make_panel(
        n_days=350, n_symbols=50, mode="fast_decay",
        horizons=(1, 5, 10, 20), decay_tau=5.0, noise=0.25,
    )
    slow = _make_panel(
        n_days=350, n_symbols=50, mode="slow_decay",
        horizons=(1, 5, 10, 20), decay_tau=30.0, noise=0.25,
    )
    hf = fit_half_life(decay_curve(fast))
    hs = fit_half_life(decay_curve(slow))
    assert hf["fitted"] and hs["fitted"], (hf, hs)
    assert hs["half_life"] > hf["half_life"], (
        f"slow={hs['half_life']} should exceed fast={hf['half_life']}"
    )


def test_ic_bounds():
    df = _make_panel(n_days=120, mode="strong", horizons=None, noise=0.4)
    ic = daily_ic(df)
    assert ((ic >= -1.0 - 1e-9) & (ic <= 1.0 + 1e-9)).all()
    # 多周期也要在界内
    df2 = _make_panel(n_days=120, mode="fast_decay", horizons=(1, 5, 20), decay_tau=8.0)
    for col in [c for c in df2.columns if c.startswith("fwd_ret")]:
        ic2 = daily_ic(df2, ret_col=col)
        assert ((ic2 >= -1.0 - 1e-9) & (ic2 <= 1.0 + 1e-9)).all(), col


def test_sample_guard_raises():
    df = _make_panel(n_days=40, n_symbols=20, mode="strong", horizons=None)
    try:
        build_report(df, name="short")
    except ValueError as e:
        assert str(MIN_IC_OBS) in str(e) or "过少" in str(e) or "少" in str(e)
        return
    raise AssertionError("过短面板未被拒绝")


def test_html_selfcontained():
    df = _make_panel(
        n_days=280, n_symbols=30, mode="fast_decay",
        horizons=(1, 5, 10, 20), decay_tau=7.0, noise=0.3,
    )
    rep = build_report(df, name="HTML_TEST")
    html = render_html(rep)
    assert "<svg" in html and "HTML_TEST" in html
    for bad in (
        'src="http', 'href="http', "<link", "<script src",
        "cdn.", "googleapis", "@import", "url(http",
    ):
        assert bad not in html, f"HTML 引用外部资源: {bad}"
    # 暖纸色调（非紫色主题）
    assert "#f6f3ec" in html or "--ground:#f6f3ec" in html
    assert "紫" not in html


def test_json_required_keys():
    df = _make_panel(
        n_days=280, n_symbols=30, mode="fast_decay",
        horizons=(1, 5, 10, 20), decay_tau=7.0,
    )
    rep = build_report(df, name="json_keys")
    required = {
        "name", "n_ic", "summary", "rolling", "decay_curve",
        "half_life_fit", "caveats", "strength", "low_sample_warning",
    }
    missing = required - set(rep.keys())
    assert not missing, f"缺键: {missing}"
    for k in ("mean_ic", "std_ic", "icir_ann", "hit_rate", "nw_t", "n"):
        assert k in rep["summary"], k
    # 可 JSON 序列化
    raw = json.dumps(_json_safe(rep), ensure_ascii=False)
    assert "mean_ic" in raw

    # load_panel 往返
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "p.csv"
        df.to_csv(p, index=False)
        loaded = load_panel(str(p))
        assert {"date", "symbol", "factor", "fwd_ret"} <= set(loaded.columns)


TESTS = [
    test_strong_factor_positive_ic,
    test_anti_factor_negative_ic,
    test_noise_factor_not_strong,
    test_fast_decay_short_half_life,
    test_slow_decay_longer_half_life,
    test_ic_bounds,
    test_sample_guard_raises,
    test_html_selfcontained,
    test_json_required_keys,
]


def main() -> int:
    ensure_demo_panel()
    passed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(TESTS)} 通过")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    sys.exit(main())

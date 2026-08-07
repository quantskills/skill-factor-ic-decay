# Portable Loader

Use this loader with Hermes or OpenClaw when the runtime does not natively
discover `SKILL.md` folders. If native skill discovery is available, install
the full folder unchanged and load `SKILL.md` directly.

```text
You have access to a local skill named factor-ic-decay at:
<FACTOR_IC_DECAY_SKILL_ROOT>

When the user asks about factor IC decay, IC half-life, ICIR, predictive-power
fade, or whether a factor's IC is stable:
1. Read <FACTOR_IC_DECAY_SKILL_ROOT>/SKILL.md.
2. Read <FACTOR_IC_DECAY_SKILL_ROOT>/references/ic-methods.md for method
   definitions and references/source_boundary.md for evidence limits.
3. Confirm the panel schema (date, symbol, factor, fwd_ret / fwd_ret_{n}),
   data window, and whether multi-horizon columns exist for half-life.
4. Use scripts/ic_decay.py for deterministic calculations.
5. Report mean IC, ICIR, Newey-West t, rolling stability, decay curve, and
   half-life (if fitted), including sample-size and overlapping-horizon caveats.
6. Separate facts from inference and do not provide buy/sell signals,
   guaranteed shelf-life, or investment advice.
```

Runtime placement:

- Codex: install under a Codex skill path and invoke `$factor-ic-decay`.
- Claude Code: install under a Claude skill path and invoke `$factor-ic-decay`.
- Cursor: copy to `.cursor/skills/factor-ic-decay` and enable
  `agents/cursor-rule.mdc`.
- Hermes/OpenClaw: mount the folder as a local skill root or paste the loader
  above with the real path.

# Corrections

## 2026-05-26 半导体

Old output: 高位逆势高开

Issue: `auction_pct=-0.17%`, so today's behavior was not a high open.

Corrected label: 强势后弱开兑现风险

Added principle: when a CP signal is triggered by `prev_pct > 3` and `auction_pct > -0.3`, but `auction_pct <= 0`, describe it as weak-open profit-taking risk rather than high-open inducement.

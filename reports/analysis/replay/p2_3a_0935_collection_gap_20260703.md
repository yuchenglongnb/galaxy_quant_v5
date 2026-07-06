# P2.3A 09:35 Collection Gap - 20260703

## Scope

This note records why P2.3A does not generate a real `stock_confirmation_0935.csv` artifact for 20260703.

## Candidate Source

```text
reports/validation/daily/20260703/signal_detail.csv
```

Status: available.

Dry-run result:

```text
candidate_count = 52
matched_count = 0
missing_count = 52
```

## Confirmation Source

Expected local source:

```text
AmazingData_Store/20260703/intraday/stock_confirmation_latest.csv
```

Status: missing.

Preferred target artifact:

```text
AmazingData_Store/20260703/intraday/stock_confirmation_0935.csv
```

Status: not generated because no local row-level 09:35 source was available.

## Gap Reason

20260703 has daily validation candidates and same-day close feedback, but it does not currently have row-level 09:35 confirmation data that can be joined back to candidate code or name.

P2.3A therefore records this as a collection gap instead of creating synthetic 09:35 data.

## Required Follow-up

One of the following collection modes is needed:

```text
historical_snapshot_query
historical_min1_kline
live_snapshot_subscription
local_existing_confirmation
```

Strict 09:35 feedback should prefer a point snapshot or 1-minute confirmation. A 09:35 five-minute K-line should not be used as a strict point-in-time 09:35 value.

## What This Does Not Support

This gap note does not support threshold changes, exemption expansion, Trend active enablement, strategy changes, or trading instructions. It only records that 20260703 still lacks row-level `auction -> same_day_0935` feedback.

# P2.3 Auction -> 09:35 Feedback Manifest

## Included Files

| Path | Role |
| --- | --- |
| `reports/temporal_feedback_matrix.py` | Adds optional 09:35 feedback ingestion |
| `tests/test_temporal_feedback_matrix.py` | Adds fixture tests for 09:35 labels, missing data, and dry-run behavior |
| `reports/analysis/evaluations/temporal_feedback_matrix_0935_seed.json` | Real 20260629 09:35 seed matrix |
| `reports/analysis/evaluations/temporal_feedback_matrix_0935_seed.md` | Human-readable 09:35 seed summary |
| `reports/analysis/replay/p2_3_0935_feedback_source_inventory.md` | Source inventory |
| `reports/analysis/replay/p2_3_auction_0935_feedback_schema.md` | Record schema and label definitions |
| `reports/analysis/replay/p2_3_auction_0935_feedback_ingestion_review.md` | Review report |
| `reports/analysis/replay/p2_3_auction_0935_feedback_manifest.md` | This manifest |

## Data Availability

Usable now:

- `20260629` daily validation rows
- `20260629` row-level 09:35 stock confirmation rows

Missing now:

- `20260703` row-level 09:35 confirmation
- `20260706` row-level 09:35 confirmation
- midday feedback
- T+1 feedback
- 5D / 10D / 20D feedback

## Date Coverage

The real seed generated in P2.3 covers:

- `20260629`

## Missing Fields

The 20260629 daily validation source has older schema characteristics. Some rows can only be joined by `name` rather than `code`.

The 09:35 confirmation source has `rs_vs_index_pct` but not a standalone benchmark return field. P2.3 records `benchmark_return_0935` as null until a future benchmark row parser is added.

## How ChatGPT Should Use This

Use the seed to inspect:

- which auction candidates were confirmed by 09:35
- which were failed by 09:35
- which candidates lacked row-level 09:35 confirmation
- which trend candidates were early-confirmed but weak versus index
- which auction decisions need midday/close follow-up

Do not use these labels as buy/sell instructions.

## Next Loop Questions

1. Can the 09:35 collection hook produce `stock_confirmation_latest.csv` for 20260703 and 20260706?
2. Should ETF / industry / index candidates have separate 09:35 confirmation sources?
3. Should `rs_vs_etf_pct` become a required confirmation field for ETF-sensitive signal families?
4. How often does 09:35 confirmation fade by midday or close?
5. Which signal families benefit most from early confirmation?

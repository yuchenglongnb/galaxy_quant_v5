# P2.4 iFinD MCP Capability Discovery

## Naming

- User-visible product name: iFinD MCP
- Provider key: `ifind_mcp`
- Historical placeholder `ths_mcp` is retained only as a rename note and is not used by new outputs.

## Exact Exposed Tools

| Exact tool | Exact arguments | Security scope | Historical support | Observed result |
|---|---|---|---|---|
| `mcp__hexin_ifind_ds_index_mcp__sector_data` | `{query: string}` | market/industry/concept sectors | yes, natural-language date range | period return and daily amount for some exact taxonomies; empty for others |
| `mcp__hexin_ifind_ds_index_mcp__index_data` | `{query: string}` | stock/fund/bond/futures/ESG indices | yes | available in schema; one prior request was platform-rate-limited |
| `mcp__hexin_ifind_ds_stock_mcp__get_stock_performance` | `{query: string}` | A-share stocks | historical daily only | schema supports daily OHLCV/return and derived indicators; not called without a candidate universe |
| `mcp__hexin_ifind_ds_stock_mcp__stock_highfreq_quotes` | `{symbols, indicators, data_mode, interval?}` | A-share stocks, max 10 symbols | no historical; current trading-day intraday only | unsuitable for historical backfill |
| `mcp__hexin_ifind_ds_index_mcp__index_highfreq_quotes` | `{symbols, indicators, data_mode, interval?}` | indices, max 10 symbols | no historical; current trading-day intraday only | unsuitable for historical 09:35 backfill |

## Field Coverage and Constraints

- `sector_data` returned daily amount and one period arithmetic-mean return. It did not return daily sector returns despite an explicit request.
- Taxonomy resolution matters. Exact queries for 创新药、光纤概念、证券 returned empty in the 20260708-20260716 run.
- Natural-language query tools do not expose a fixed response table schema; every response must be parsed and field-validated.
- The high-frequency tools have explicit symbol limits and do not support historical dates.
- No credential, token, cookie, account, or host field is stored.

## Candidate-level Decision

No candidate-level iFinD query was run. Candidate universes are missing for 20260708 onward, and the project forbids a full-market dump.

```text
candidate_level_ifind_data = false
validation_level = sector_only
```

Sector records may support price-turnover observations, but cannot be represented as daily candidate validation.

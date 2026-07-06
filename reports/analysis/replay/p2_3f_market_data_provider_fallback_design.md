# P2.3F Market Data Provider Fallback Design

## Scope

This design keeps the P2.3A-E artifact contract stable while allowing future 09:35 feedback collection to use another provider if AmazingData remains blocked.

## Stable Output Contract

All providers must write the same timepoint-specific artifacts:

```text
AmazingData_Store/<date>/intraday/stock_confirmation_0935.csv
AmazingData_Store/<date>/intraday/stock_confirmation_0935_meta.json
```

The directory name remains stable for now because downstream temporal matrix ingestion already reads from this contract. Provider identity is recorded in metadata.

## Provider Interface

```text
MarketDataProvider0935
- provider_name
- supports_snapshot_0935
- supports_min1_0935
- query_candidate_0935(date, candidates, mode)
- normalize_to_stock_confirmation_0935(rows)
```

## Meta Fields

```json
{
  "provider": "amazingdata | ths_mcp",
  "provider_status": "ok | blocked | fallback_used",
  "collection_mode": "historical_snapshot_query | historical_min1_kline | provider_mcp_query",
  "data_source": "amazingdata_query_snapshot | amazingdata_query_kline_min1 | ths_mcp_snapshot | ths_mcp_min1"
}
```

## THS MCP Adapter Readiness

The THS MCP adapter is design-only in P2.3F. No real MCP call is made.

Required future capability:

```text
candidate code list input
date input
09:35 snapshot or 1-minute bar output
candidate-only query
no full-market dump
no token/key/cookie/account value in repo
```

## Decision Rule

If AmazingData remains without `safe_to_query=true`, the next implementation step can add a provider adapter:

```text
ths_mcp -> provider_mcp_query -> stock_confirmation_0935.csv/meta -> temporal matrix
```

The temporal matrix does not need to be rewritten.

## Boundary

This design does not include credentials, live MCP calls, full-market data dumps, trading instructions, strategy changes, threshold changes, lesson writes, pattern writes, or registry writes.

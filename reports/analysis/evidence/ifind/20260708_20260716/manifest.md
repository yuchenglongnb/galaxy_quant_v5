# iFinD Sector Evidence Manifest

- Provider: `ifind_mcp`
- Visible name: iFinD MCP
- Date range: 20260708-20260716
- Validation level: `sector_only`
- Candidate-level data generated: no
- Source tool: `mcp__hexin_ifind_ds_index_mcp__sector_data`

## Coverage

- 半导体设备: period return and daily amount available.
- 机器人概念: period return and daily amount available.
- 创新药、光纤概念、证券: empty results for the requested taxonomy/range.

The tool returned period-level arithmetic mean return, not daily return. Daily amount is preserved as returned. These records must not be written into `reports/validation/daily/<date>/signal_detail.csv`.

## Interpretation Boundary

- 半导体设备: `price_without_turnover_confirmation` over this range.
- 机器人概念: `weak_or_cooling` over this range.
- Empty results remain `insufficient_sector_evidence`.
- No candidate-level signal result, trading conclusion, threshold change, or active gate change is supported.

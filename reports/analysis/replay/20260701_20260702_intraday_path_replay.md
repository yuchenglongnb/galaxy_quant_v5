# 20260701-20260702 Intraday Path Replay

This report is analysis-only. It does not justify deterministic rule changes, CP threshold changes, exemption expansion, Trend active enablement, or trading advice.

## Scope and Data Inputs

- Date range: 20260701 to 20260702
- This replay uses local cached OHLC and validation outputs only.

- 20260701: `reports\validation\derived\signal_detail_manual_code_patch\20260701_signal_detail.manual_code_patch.csv` (manual_code_patch), rows=85
  - quote: `AmazingData_Store\20260701\stocks.csv`
  - quote: `AmazingData_Store\20260701\indices.csv`
- 20260702: `reports\validation\daily\20260702\signal_detail.csv` (daily_signal_detail), rows=90
  - quote: `AmazingData_Store\20260702\stocks.csv`
  - quote: `AmazingData_Store\20260702\indices.csv`

## Field Definitions

- `open_to_high_pct`: intraday high versus open.
- `open_to_low_pct`: intraday low versus open.
- `close_to_high_drawdown_pct`: close versus intraday high.
- `intraday_range_pct`: high versus low.
- `mfe_pct` / `mae_pct`: validation-only open-to-high and open-to-low aliases.
- `signal_path_type`: conservative OHLC path label.

## 20260701 Intraday Path Summary

|signal_family|count|avg_body_pct|median_body_pct|avg_open_to_high_pct|avg_open_to_low_pct|avg_close_to_high_drawdown_pct|path_type_distribution|
|---|---|---|---|---|---|---|---|
|CP风险|10|-1.4849|-2.2231|2.5387|-2.4144|-3.2724|low_open_rebound_failed:3, range_chop:2, unknown:2, high_open_trap:1, rush_up_fade:1, close_near_high:1|
|反核机会|8|-0.0465|-0.1575|2.5437|-3.5491|-2.1318|range_chop:4, close_near_low:1, close_near_high:1, one_way_selloff:1, unknown:1|
|趋势机会|67|-0.2509|0.2865|3.3358|-3.1565|-3.5273|range_chop:32, low_open_rebound_failed:12, rush_up_fade:9, one_way_selloff:6, high_open_trap:5, unknown:2, close_near_high:1|

## 20260702 Intraday Path Summary

|signal_family|count|avg_body_pct|median_body_pct|avg_open_to_high_pct|avg_open_to_low_pct|avg_close_to_high_drawdown_pct|path_type_distribution|
|---|---|---|---|---|---|---|---|
|CP风险|7|-1.2236|-0.6192|0.8447|-1.7912|-2.1207|one_way_selloff:2, range_chop:2, high_open_trap:1, close_near_high:1, close_near_low:1|
|反核机会|31|-2.1362|-2.4186|2.0898|-2.8940|-4.1564|low_open_rebound_failed:12, close_near_low:5, one_way_selloff:5, range_chop:5, unknown:3, rush_up_fade:1|
|趋势机会|52|-1.3714|-1.9707|3.1930|-2.7984|-4.3275|low_open_rebound_failed:13, rush_up_fade:10, high_open_trap:9, close_near_low:7, one_way_selloff:5, range_chop:5, unknown:3|

## 20260701 -> 20260702 T+1 Path Replay

|signal_family|resolved_count|avg_t1_open_return|avg_t1_close_return|t1_close_positive_rate|avg_t1_open_to_low_pct|avg_t1_close_to_high_drawdown_pct|t1_path_type_distribution|
|---|---|---|---|---|---|---|---|
|CP风险|8|-3.6264|-6.8874|0.0000|-4.0224|-4.7922|low_open_rebound_failed:4, one_way_selloff:2, range_chop:1, rush_up_fade:1|
|反核机会|7|-0.5903|-1.3880|33.3333|-2.4321|-2.6377|range_chop:3, one_way_selloff:3, low_open_rebound_failed:1|
|趋势机会|63|-0.8122|-1.3935|16.6667|-2.6915|-4.6260|rush_up_fade:33, range_chop:14, close_near_low:11, one_way_selloff:5|

## Signal-level Interpretation

- CP风险: use path labels to inspect whether risk samples were one-way selloff, high-open trap, or failed rebound; this remains posterior validation only.
- 反核机会: inspect whether low-open samples rebounded intraday but failed by close; no trigger adjustment is implied.
- 趋势机会: inspect whether trend candidates rushed upward then faded or closed near lows; Trend active remains governed by confirmation coverage, ETF benchmark evidence, and shadow gate.

## Top-retreat Case Study

|date|name|code|auction_pct|body_pct|open_to_high_pct|open_to_low_pct|close_to_high_drawdown_pct|intraday_range_pct|signal_path_type|observation|
|---|---|---|---|---|---|---|---|---|---|---|
|20260701|科创50|000688.SH|-0.1001|-2.3853|2.2484|-3.8670|-4.5319|6.3614|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260701|创业板|399006.SZ|-0.1509|-1.7398|0.5919|-2.6276|-2.3179|3.3064|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260701|半导体设备 ETF|159516.SZ|0.0000|0.9114|6.6329|-1.4177|-5.3656|8.1664|rush_up_fade|该路径显示盘中上冲后回落。|
|20260701|半导体 ETF|512480.SH|0.0000|-2.0632|3.5940|-3.4942|-5.4610|7.3448|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260701|消费电子 ETF|159732.SZ|0.0000|-2.3958|1.9792|-3.8021|-4.2901|6.0097|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260701|金融科技|159851.SZ|0.1605|4.8077|6.7308|-0.4808|-1.8018|7.2464|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260701|证券|512880.SH|-0.3552|4.8128|6.1497|-0.2674|-1.2594|6.4343|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260702|科创50|000688.SH|-4.3262|-3.5248|2.2036|-3.9603|-5.6049|6.4181|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260702|创业板|399006.SZ|-2.9427|-2.8551|0.8108|-3.2833|-3.6365|4.2331|close_near_low|该样本收盘贴近低位，显示日内承接偏弱。|
|20260702|半导体设备 ETF|159516.SZ|-6.4225|-3.8070|3.4316|-3.8070|-6.9984|7.5251|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260702|半导体 ETF|512480.SH|-4.8590|-3.5714|2.3929|-4.6429|-5.8249|7.3783|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260702|消费电子 ETF|159732.SZ|-3.9488|-3.4444|0.5556|-3.8889|-3.9779|4.6243|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|
|20260702|金融科技|159851.SZ|0.4587|-3.8052|0.1522|-4.1096|-3.9514|4.4444|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|
|20260702|证券|512880.SH|-0.0850|-2.1277|0.1702|-2.5532|-2.2940|2.7948|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|

## Limitations

- Only local closed-day cache is used.
- The sample window is limited to 20260701-20260702.
- Path labels are validation descriptors, not strategy rules.

## Next Step Recommendation

P1.5C: Broader-window Intraday Path Distribution Validation. Keep it analysis-only until enough samples support any future rule proposal.

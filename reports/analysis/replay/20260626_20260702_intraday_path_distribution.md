# 20260626-20260702 Intraday Path Distribution Validation

This report is analysis-only. It does not justify deterministic rule changes, CP threshold changes, exemption expansion, Trend active enablement, or trading advice.

## Scope and Safety Boundary

- This is a validation/reporting framework, not a strategy-change workflow.
- It does not change CP threshold, CP exemption, reversal trigger, Trend active status, ranking, shortlist, evaluator logic, lesson files, pattern files, or registry files.

## Input Coverage Table

|date|signal_detail_quality|signal_rows|stocks_ohlc_present|indices_ohlc_present|path_fields_computed_from_ohlc|t1_next_date|t1_next_day_ohlc_available|notes|
|---|---|---|---|---|---|---|---|---|
|20260626|daily_signal_detail|51|True|True|True|20260629|True|usable|
|20260629|manual_code_patch|27|True|True|True|20260630|True|usable|
|20260630|manual_code_patch|30|True|True|True|20260701|True|usable|
|20260701|manual_code_patch|85|True|True|True|20260702|True|usable|
|20260702|daily_signal_detail|90|True|True|True||False|usable|

## Metric Definition and Denominator Reconciliation

|metric|definition|
|---|---|
|`body_pct`|Same-day open-to-close body return: close / open - 1.|
|`close_pct`|Same-day close return versus previous close when source output provides it.|
|`gap_pct`|Open versus previous close when pre_close is available.|
|`close_from_prev_close_pct`|Close versus previous close when pre_close is available.|
|`t1_body_pct`|T+1 close / T+1 open - 1, used by intraday path fields.|
|`t1_open_return`|T+1 open / T+1 pre_close - 1.|
|`t1_close_return`|T+1 close / T+1 pre_close - 1.|
|`t1_close_positive_rate`|Share of resolved code-joined candidates with t1_close_return > 0.|

P1.5B t1_close_return is computed from T+1 close versus T+1 pre_close. Earlier manual summaries may have mixed close/open body return, close-vs-prior-close return, or different resolved denominators.
- manual_resolution_scope=industry_without_code is excluded from code-level denominator.
- manual_resolution_status=pending is counted as pending_blocked and excluded from resolved denominator.
- primary code join is required for T+1 return metrics.
- name fallback is not used in this analysis framework.
- unmatched rows are counted explicitly and excluded from return metrics.

## Broader-window Daily Summary

|date|signal_family|count|avg_body_pct|positive_body_rate|avg_open_to_low_pct|avg_close_to_high_drawdown_pct|path_type_distribution|
|---|---|---|---|---|---|---|---|
|20260626|反核机会|23|-1.5954|21.7391|-3.4304|-2.9192|unknown:14, one_way_selloff:5, range_chop:2, low_open_rebound_failed:1, close_near_low:1|
|20260626|趋势机会|28|-1.4246|39.2857|-3.9750|-5.0340|range_chop:7, rush_up_fade:6, low_open_rebound_failed:6, one_way_selloff:4, unknown:2, high_open_trap:2, close_near_low:1|
|20260629|CP风险|5|6.0737|100.0000|-3.0256|-0.5792|close_near_high:3, range_chop:2|
|20260629|反核机会|9|1.2442|66.6667|-1.8270|-1.1146|close_near_high:5, low_open_rebound_failed:2, range_chop:2|
|20260629|趋势机会|13|2.0756|61.5385|-3.6151|-2.5627|range_chop:5, high_open_trap:3, close_near_high:3, low_open_rebound_failed:1, unknown:1|
|20260630|CP风险|8|2.6907|75.0000|-2.2337|-1.0309|close_near_high:4, range_chop:3, high_open_trap:1|
|20260630|反核机会|15|0.9320|66.6667|-1.2505|-0.6795|range_chop:8, close_near_high:6, unknown:1|
|20260630|趋势机会|7|1.8143|85.7143|-2.0827|-1.7325|range_chop:5, close_near_high:1, low_open_rebound_failed:1|
|20260701|CP风险|10|-1.4849|30.0000|-2.4144|-3.2724|low_open_rebound_failed:3, range_chop:2, unknown:2, high_open_trap:1, rush_up_fade:1, close_near_high:1|
|20260701|反核机会|8|-0.0465|50.0000|-3.5491|-2.1318|range_chop:4, close_near_low:1, close_near_high:1, one_way_selloff:1, unknown:1|
|20260701|趋势机会|67|-0.2509|53.7313|-3.1565|-3.5273|range_chop:32, low_open_rebound_failed:12, rush_up_fade:9, one_way_selloff:6, high_open_trap:5, unknown:2, close_near_high:1|
|20260702|CP风险|7|-1.2236|0.0000|-1.7912|-2.1207|one_way_selloff:2, range_chop:2, high_open_trap:1, close_near_high:1, close_near_low:1|
|20260702|反核机会|31|-2.1362|16.1290|-2.8940|-4.1564|low_open_rebound_failed:12, close_near_low:5, one_way_selloff:5, range_chop:5, unknown:3, rush_up_fade:1|
|20260702|趋势机会|52|-1.3714|25.0000|-2.7984|-4.3275|low_open_rebound_failed:13, rush_up_fade:10, high_open_trap:9, close_near_low:7, one_way_selloff:5, range_chop:5, unknown:3|

## Signal-family Path Distribution

|signal_family|count|avg_body_pct|positive_body_rate|avg_open_to_low_pct|avg_close_to_high_drawdown_pct|path_type_distribution|
|---|---|---|---|---|---|---|
|CP风险|30|0.9493|46.6667|-2.3161|-1.8631|close_near_high:9, range_chop:9, high_open_trap:3, low_open_rebound_failed:3, unknown:2, one_way_selloff:2, rush_up_fade:1, close_near_low:1|
|反核机会|86|-0.9083|34.8837|-2.5477|-2.6436|range_chop:21, unknown:19, low_open_rebound_failed:15, close_near_high:12, one_way_selloff:11, close_near_low:7, rush_up_fade:1|
|趋势机会|167|-0.5289|44.3114|-3.1673|-3.8685|range_chop:54, low_open_rebound_failed:33, rush_up_fade:25, high_open_trap:19, one_way_selloff:15, unknown:8, close_near_low:8, close_near_high:5|

## Date-phase Path Distribution

|phase_bucket|signal_family|count|avg_body_pct|avg_open_to_low_pct|avg_close_to_high_drawdown_pct|path_type_distribution|
|---|---|---|---|---|---|---|
|pre_retreat_setup|CP风险|13|3.9918|-2.5383|-0.8571|close_near_high:7, range_chop:5, high_open_trap:1|
|pre_retreat_setup|反核机会|47|-0.2450|-2.0257|-1.4318|unknown:15, range_chop:12, close_near_high:11, one_way_selloff:5, low_open_rebound_failed:3, close_near_low:1|
|pre_retreat_setup|趋势机会|48|-0.0043|-3.5847|-3.8614|range_chop:17, low_open_rebound_failed:8, rush_up_fade:6, high_open_trap:5, close_near_high:4, one_way_selloff:4, unknown:3, close_near_low:1|
|retreat_confirmation|CP风险|7|-1.2236|-1.7912|-2.1207|one_way_selloff:2, range_chop:2, high_open_trap:1, close_near_high:1, close_near_low:1|
|retreat_confirmation|反核机会|31|-2.1362|-2.8940|-4.1564|low_open_rebound_failed:12, close_near_low:5, one_way_selloff:5, range_chop:5, unknown:3, rush_up_fade:1|
|retreat_confirmation|趋势机会|52|-1.3714|-2.7984|-4.3275|low_open_rebound_failed:13, rush_up_fade:10, high_open_trap:9, close_near_low:7, one_way_selloff:5, range_chop:5, unknown:3|
|retreat_transition|CP风险|10|-1.4849|-2.4144|-3.2724|low_open_rebound_failed:3, range_chop:2, unknown:2, high_open_trap:1, rush_up_fade:1, close_near_high:1|
|retreat_transition|反核机会|8|-0.0465|-3.5491|-2.1318|range_chop:4, close_near_low:1, close_near_high:1, one_way_selloff:1, unknown:1|
|retreat_transition|趋势机会|67|-0.2509|-3.1565|-3.5273|range_chop:32, low_open_rebound_failed:12, rush_up_fade:9, one_way_selloff:6, high_open_trap:5, unknown:2, close_near_high:1|

## T+1 Broader-window Replay

|prev_date|date|candidate_count|resolved_code_denominator|manual_scope_excluded_count|pending_blocked_count|primary_code_join_count|fallback_name_join_count|unmatched_count|
|---|---|---|---|---|---|---|---|---|
|20260626|20260629|51|0|0|0|0|0|51|
|20260629|20260630|27|25|1|1|25|0|0|
|20260630|20260701|30|29|1|0|29|0|0|
|20260701|20260702|85|78|5|2|78|0|0|

|signal_family|resolved_count|avg_t1_close_return|median_t1_close_return|t1_close_positive_rate|avg_t1_open_to_low_pct|avg_t1_close_to_high_drawdown_pct|t1_path_type_distribution|
|---|---|---|---|---|---|---|---|
|CP风险|21|-3.1001|-3.0444|28.5714|-3.7557|-3.8693|low_open_rebound_failed:6, range_chop:5, rush_up_fade:4, close_near_high:3, one_way_selloff:2, high_open_trap:1|
|反核机会|29|0.5949|0.2640|57.6923|-1.4142|-1.6371|range_chop:21, close_near_high:3, one_way_selloff:3, rush_up_fade:1, low_open_rebound_failed:1|
|趋势机会|82|-0.1679|-0.6469|37.5000|-2.5717|-4.0157|rush_up_fade:35, range_chop:27, close_near_low:11, one_way_selloff:6, close_near_high:3|

## Comparison with P1.5B Two-day Replay

P1.5B used a focused 20260701-20260702 sample. This broader report keeps the same metric definitions but adds input coverage, denominator reconciliation, and phase buckets. Differences versus earlier manual summaries should be read as denominator or metric-base differences unless reconciled by row-level audit.

## Representative Cases

|date|name|code|auction_pct|body_pct|open_to_high_pct|open_to_low_pct|close_to_high_drawdown_pct|signal_path_type|observation|
|---|---|---|---|---|---|---|---|---|---|
|20260626|科创50|000688.SH|-1.5437|-0.1056|2.0661|-2.8268|-2.1277|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260626|创业板|399006.SZ|-1.2026|-2.8986|0.2151|-3.3345|-3.1070|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|
|20260626|半导体设备 ETF|159516.SZ|-0.8226|4.3839|5.9242|-0.3555|-1.4541|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260626|半导体 ETF|512480.SH|-1.5862|0.6227|2.9670|-2.1978|-2.2768|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260626|消费电子 ETF|159732.SZ|-1.8047|-0.8108|1.6216|-2.7027|-2.3936|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260626|金融科技|159851.SZ|-1.0574|-4.8855|0.4580|-4.8855|-5.3191|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|
|20260626|证券|512880.SH|-0.6092|-3.0648|1.3135|-3.2399|-4.3215|close_near_low|该样本收盘贴近低位，显示日内承接偏弱。|
|20260629|科创50|000688.SH|0.3633|4.2332|4.3210|-1.2823|-0.0841|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260629|创业板|399006.SZ|0.1541|0.3815|1.5424|-2.3101|-1.1432|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260629|半导体设备 ETF|159516.SZ|1.5891|7.3184|7.6536|-1.6760|-0.3114|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260629|半导体 ETF|512480.SH|0.5461|5.3222|5.4308|-2.2448|-0.1030|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260629|消费电子 ETF|159732.SZ|0.0545|0.2179|3.1046|-4.4118|-2.7998|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260629|金融科技|159851.SZ|-0.4815|-0.3226|1.4516|-1.6129|-1.7488|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260629|证券|512880.SH|0.6323|0.8079|2.0646|-0.6284|-1.2313|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260630|科创50|000688.SH|0.3232|3.5156|3.8319|-0.8876|-0.3047|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260630|创业板|399006.SZ|0.0222|2.9656|3.2120|-0.2819|-0.2387|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260630|半导体设备 ETF|159516.SZ|-0.3644|3.1870|3.5005|-2.1421|-0.3029|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260630|半导体 ETF|512480.SH|0.0000|3.3001|3.5064|-2.4407|-0.1993|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260630|消费电子 ETF|159732.SZ|-0.1630|4.5182|5.0082|-0.4355|-0.4666|close_near_high|该样本收盘贴近高位，未呈现典型退潮路径。|
|20260630|金融科技|159851.SZ|-0.4854|1.3008|2.1138|-1.3008|-0.7962|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260630|证券|512880.SH|-0.6233|0.8961|1.4337|-0.6272|-0.5300|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260701|科创50|000688.SH|-0.1001|-2.3853|2.2484|-3.8670|-4.5319|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260701|创业板|399006.SZ|-0.1509|-1.7398|0.5919|-2.6276|-2.3179|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260701|半导体设备 ETF|159516.SZ|0.0000|0.9114|6.6329|-1.4177|-5.3656|rush_up_fade|该路径显示盘中上冲后回落。|
|20260701|半导体 ETF|512480.SH|0.0000|-2.0632|3.5940|-3.4942|-5.4610|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260701|消费电子 ETF|159732.SZ|0.0000|-2.3958|1.9792|-3.8021|-4.2901|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260701|金融科技|159851.SZ|0.1605|4.8077|6.7308|-0.4808|-1.8018|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260701|证券|512880.SH|-0.3552|4.8128|6.1497|-0.2674|-1.2594|range_chop|该样本为区间震荡路径，需要放入更大窗口比较。|
|20260702|科创50|000688.SH|-4.3262|-3.5248|2.2036|-3.9603|-5.6049|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260702|创业板|399006.SZ|-2.9427|-2.8551|0.8108|-3.2833|-3.6365|close_near_low|该样本收盘贴近低位，显示日内承接偏弱。|
|20260702|半导体设备 ETF|159516.SZ|-6.4225|-3.8070|3.4316|-3.8070|-6.9984|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260702|半导体 ETF|512480.SH|-4.8590|-3.5714|2.3929|-4.6429|-5.8249|low_open_rebound_failed|该样本显示盘中反抽不足以修复收盘弱势。|
|20260702|消费电子 ETF|159732.SZ|-3.9488|-3.4444|0.5556|-3.8889|-3.9779|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|
|20260702|金融科技|159851.SZ|0.4587|-3.8052|0.1522|-4.1096|-3.9514|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|
|20260702|证券|512880.SH|-0.0850|-2.1277|0.1702|-2.5532|-2.2940|one_way_selloff|该样本表现为开盘后继续走弱，支持退潮样本的后验观察。|

## Limitations

- Only local closed-day cache is used.
- The sample window is limited by locally available signal_detail and OHLC files.
- Path labels are validation descriptors, not strategy rules.
- Earlier dates without code-backfilled signal_detail may have lower T+1 code-keyed coverage.

## Next Step Recommendation

P1.5D: Broader-window Path Stability Review and Rule-Proposal Gate Design. Keep it analysis-only; design gates for future proposals instead of modifying rules.

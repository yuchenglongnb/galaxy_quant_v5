# Index Min1 Probe 20260604

## 1. Probe Scope

- timeout_sec: `20`
- query_window.start: `20260604 09:30:00`
- query_window.end: `20260604 10:00:00`
- query_window.period: `min1`
- query_window_effective: `full_day_query_kline_call_in_current_implementation`

## 2. Per-Code Result

| code | status | elapsed_sec | row_count | first_trade_time | last_trade_time | error |
| ---- | ------ | ----------: | --------: | ---------------- | --------------- | ----- |
| 000001.SH | failed | 3.7157 | 0 | - | - | waring: [Errno 13] Permission denied: 'C:\\Users\\Public\\Documents\\mdga_file\\.ca.crt'
TGW log: level: 4     log:   CheckLogonLegal | CheckLogonLegal server_vip is empty or over kIPMaxLen
TGW log: level: 4     log:   Check Init | The internet mode of tgw init failed.
login fail
TGW log: level: 4     log:   SetThirdInfoParam check | Program is not inited
TGW log: level: 4     log:   SetThirdInfoParam check | Program is not inited |
| 000688.SH | failed | 3.6106 | 0 | - | - | waring: [Errno 13] Permission denied: 'C:\\Users\\Public\\Documents\\mdga_file\\.ca.crt'
TGW log: level: 4     log:   CheckLogonLegal | CheckLogonLegal server_vip is empty or over kIPMaxLen
TGW log: level: 4     log:   Check Init | The internet mode of tgw init failed.
login fail
TGW log: level: 4     log:   SetThirdInfoParam check | Program is not inited
TGW log: level: 4     log:   SetThirdInfoParam check | Program is not inited |
| 399006.SZ | failed | 3.4612 | 0 | - | - | waring: [Errno 13] Permission denied: 'C:\\Users\\Public\\Documents\\mdga_file\\.ca.crt'
TGW log: level: 4     log:   CheckLogonLegal | CheckLogonLegal server_vip is empty or over kIPMaxLen
TGW log: level: 4     log:   Check Init | The internet mode of tgw init failed.
login fail
TGW log: level: 4     log:   SetThirdInfoParam check | Program is not inited
TGW log: level: 4     log:   SetThirdInfoParam check | Program is not inited |

## 3. Failure Summary

| status | count |
| ------- | ----: |
| success | 0 |
| empty | 0 |
| timeout | 0 |
| failed | 3 |

## 4. Diagnosis

- diagnosis: `all_failed`

## 5. Recommended Next Step

- per-code probe 在查询前即失败，优先检查子进程 TGW / AmazingData 初始化与登录环境。
- 在确认子进程可独立登录前，不要把失败归因到 index code 或 min1 路径本身。
# Data Availability 20260717

- trading_day_confirmed: true (`CalendarHelper.generate_workday_calendar`)
- market_close_time_passed: true
- market_closed_confirmed: false (closed cache is absent)
- stocks / indices: missing / missing
- auction review / signal detail / signal metrics: missing / missing / missing
- candidate universe: unavailable
- candidate query attempted: false
- AmazingData candidate path: blocked by prior login-control-flow or permission evidence; no retry
- iFinD sector result: empty
- validation level: `missing`

Passing the market close clock does not establish closed evidence when the required cache and validation artifacts are absent.

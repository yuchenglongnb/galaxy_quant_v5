# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.getcwd())

import AmazingData as ad

from config.settings import DBConfig
from core.calendar_helper import CalendarHelper
from core.intraday_monitor import IntradayMonitor


def main():
    out_path = os.path.join("reports", "verification", "20260608", "inspect_kline_debug.txt")
    ad.login(
        username=DBConfig.USERNAME,
        password=DBConfig.PASSWORD,
        host=DBConfig.IP,
        port=DBConfig.PORT,
    )
    try:
        cal = CalendarHelper.generate_workday_calendar(days=30)
        md = ad.MarketData(cal)
        result = md.query_kline(["300308.SZ"], 20260608, 20260608, ad.constant.Period.min1.value)
        lines = [str(type(result))]
        if isinstance(result, dict):
            lines.append(str(list(result.keys())[:3]))
            if result:
                first = list(result.values())[0]
                lines.append(str(first.columns.tolist()))
                lines.append(first.head(8).to_string())
        monitor = IntradayMonitor()
        helper_df = monitor._fetch_opening_minute_bars(["300308.SZ"], 20260608)
        lines.append("HELPER_ROWS=" + str(len(helper_df)))
        if not helper_df.empty:
            lines.append(helper_df.head(8).to_string())
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    finally:
        ad.logout(DBConfig.USERNAME)


if __name__ == "__main__":
    main()

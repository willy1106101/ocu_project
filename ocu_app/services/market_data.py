from __future__ import annotations

from typing import Any, Dict

import yfinance as yf


def _safe_round(value: Any, digits: int = 2) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def get_etf_snapshot(
    ticker_yfinance: str,
    one_year_period: str = "1y",
    recent_period: str = "5d",
) -> Dict[str, float]:
    """
    回傳 ETF 所需展示資料，集中處理外部資料錯誤，避免頁面因為 yfinance 異常而崩潰。
    """
    snapshot = {
        "current_price": 0.0,
        "open_price": 0.0,
        "change_percent": 0.0,
        "yesterday_close": 0.0,
        "annual_return": 0.0,
        "amplitude": 0.0,
    }

    try:
        ticker = yf.Ticker(ticker_yfinance)
        yearly_hist = ticker.history(period=one_year_period)
        recent_hist = ticker.history(period=recent_period)

        if yearly_hist.empty and recent_hist.empty:
            return snapshot

        latest_source = yearly_hist if not yearly_hist.empty else recent_hist
        latest_row = latest_source.iloc[-1]

        current_price = float(latest_row.get("Close", 0.0))
        open_price = float(latest_row.get("Open", 0.0))

        snapshot["current_price"] = _safe_round(current_price)
        snapshot["open_price"] = _safe_round(open_price)

        if not yearly_hist.empty:
            price_col = "Adj Close" if "Adj Close" in yearly_hist.columns else "Close"
            start_price = float(yearly_hist[price_col].iloc[0])
            end_price = float(yearly_hist[price_col].iloc[-1])
            if start_price > 0:
                snapshot["annual_return"] = _safe_round(
                    ((end_price - start_price) / start_price) * 100
                )

        for source in (yearly_hist, recent_hist):
            if not source.empty and len(source) >= 2:
                previous_close = float(source["Close"].iloc[-2])
                if previous_close <= 0:
                    continue

                high_price = float(source["High"].iloc[-1])
                low_price = float(source["Low"].iloc[-1])
                change_percent = ((current_price - previous_close) / previous_close) * 100
                amplitude = ((high_price - low_price) / previous_close) * 100

                snapshot["yesterday_close"] = _safe_round(previous_close)
                snapshot["change_percent"] = _safe_round(change_percent)
                snapshot["amplitude"] = _safe_round(amplitude)
                break

        return snapshot
    except Exception:
        return snapshot

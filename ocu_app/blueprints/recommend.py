from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
import pandas as pd
import yfinance as yf

from ..core.config import AppConfig
from ..core.decorators import login_required
from ..core.models import DatabaseConnectionError, get_db_connection

recommend_bp = Blueprint("recommend", __name__)


@recommend_bp.route("/recommend")
@login_required
def recommend_home():
    user_risk = session.get("risk_level", "中風險")
    risk_map = AppConfig.RISK_TYPE_MAP
    target_types = risk_map.get(user_risk, risk_map.get("中風險", (2,)))
    recommend_limit = max(1, int(AppConfig.RECOMMEND_ETF_LIMIT))

    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            format_strings = ",".join(["%s"] * len(target_types))
            cursor.execute(
                f"""
                SELECT t.name, t.ticker, t.ticker_yfinance, ty.name AS type_name
                FROM etf_tickers t
                JOIN etf_types ty ON t.types = ty.id
                WHERE t.types IN ({format_strings})
                LIMIT {recommend_limit}
                """,
                tuple(target_types),
            )
            recommended_etfs = cursor.fetchall()

            cursor.execute(
                """
                SELECT ticker, name, ticker_yfinance
                FROM etf_tickers
                ORDER BY ticker ASC
                """
            )
            all_etfs = cursor.fetchall()

        return render_template(
            "recommend.html",
            etfs=recommended_etfs,
            all_etfs=all_etfs,
            user_risk=user_risk,
        )
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
        return redirect(url_for("home"))
    except Exception as exc:
        current_app.logger.exception("Load recommendation failed: %s", exc)
        flash("推薦資料讀取失敗，請稍後再試。", "danger")
        return redirect(url_for("home"))
    finally:
        if db:
            db.close()


@recommend_bp.route("/compare", methods=["POST"])
@login_required
def compare_etfs():
    ticker1 = request.form.get("etf1")
    ticker2 = request.form.get("etf2")

    if not ticker1 or not ticker2:
        flash("請選擇兩檔 ETF。", "warning")
        return redirect(url_for("recommend.recommend_home"))

    if ticker1 == ticker2:
        flash("請選擇不同的兩檔 ETF 進行比較。", "warning")
        return redirect(url_for("recommend.recommend_home"))

    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT ticker, ticker_yfinance, name
                FROM etf_tickers
                WHERE ticker_yfinance = %s OR ticker_yfinance = %s
                """,
                (ticker1, ticker2),
            )
            detail_etfs = cursor.fetchall()

        ticker_name_map = {
            item["ticker_yfinance"]: [item["name"], item["ticker"]] for item in detail_etfs
        }
        etf1 = ticker_name_map.get(ticker1, [ticker1, ticker1])
        etf2 = ticker_name_map.get(ticker2, [ticker2, ticker2])

        compare_period = AppConfig.COMPARE_PERIOD
        df1 = yf.Ticker(ticker1).history(period=compare_period)
        df2 = yf.Ticker(ticker2).history(period=compare_period)

        if df1.empty or df2.empty:
            flash("價格資料不足，暫時無法比較。", "warning")
            return redirect(url_for("recommend.recommend_home"))

        for dataframe in (df1, df2):
            dataframe["y_close"] = dataframe["Close"].shift(1)
            dataframe["amplitude"] = (
                (dataframe["High"] - dataframe["Low"]) / dataframe["y_close"] * 100
            )

        df1 = df1.reset_index()[["Date", "amplitude"]]
        df2 = df2.reset_index()[["Date", "amplitude"]]
        merged = pd.merge(df1, df2, on="Date", suffixes=("_1", "_2"))

        corr = merged["amplitude_1"].corr(merged["amplitude_2"])
        corr = None if corr is None or pd.isna(corr) else round(float(corr), 3)

        return render_template(
            "compare_result.html",
            etf1_code=etf1,
            etf2_code=etf2,
            amplitude_corr=corr,
        )
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
    except Exception as exc:
        current_app.logger.exception("ETF comparison failed: %s", exc)
        flash("比較失敗，請稍後再試。", "danger")
    finally:
        if db:
            db.close()

    return redirect(url_for("recommend.recommend_home"))

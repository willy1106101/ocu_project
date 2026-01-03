from flask import Blueprint, render_template, request, session, redirect, url_for
from models import get_db_connection
import yfinance as yf
import pandas as pd

recommend_bp = Blueprint('recommend', __name__)

@recommend_bp.route('/recommend')
def recommend_home():
    user_risk = session.get('risk_level', '中風險')
    risk_map = {
        '低風險': (1,), 
        '中風險': (2, 4, 10), 
        '高風險': (3, 7, 8)
    }
    target_types = risk_map.get(user_risk, (2,))

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # --- 修正後的 SQL：使用 JOIN 抓取類型名稱 ---
            format_strings = ','.join(['%s'] * len(target_types))
            sql = f"""
                SELECT t.name, t.ticker, t.ticker_yfinance, ty.name as type_name 
                FROM etf_tickers t
                JOIN etf_types ty ON t.types = ty.id
                WHERE t.types IN ({format_strings}) 
                LIMIT 6
            """
            cursor.execute(sql, target_types)
            recommended_etfs = cursor.fetchall()
            
            # 抓取所有 ETF 供下拉選單
            cursor.execute("SELECT ticker, name, ticker_yfinance FROM etf_tickers ORDER BY ticker ASC")
            all_etfs = cursor.fetchall()
            
        return render_template('recommend.html', 
                               etfs=recommended_etfs, 
                               all_etfs=all_etfs, 
                               user_risk=user_risk)
    finally:
        db.close()


@recommend_bp.route('/compare', methods=['POST'])
def compare_etfs():
    ticker1 = request.form.get('etf1')
    ticker2 = request.form.get('etf2')
    db = get_db_connection()
    try:
        # 1️⃣ 從資料庫抓 ETF 名稱
        with db.cursor() as cursor:
            sql = """
                SELECT ticker, ticker_yfinance, name
                FROM etf_tickers
                WHERE ticker_yfinance = %s OR ticker_yfinance = %s
            """
            cursor.execute(sql, (ticker1, ticker2))
            detail_etfs = cursor.fetchall()

        # 轉成字典方便查找名稱
        ticker_name_map = {d['ticker_yfinance']: [d['name'],d['ticker']] for d in detail_etfs}
        etf1 = ticker_name_map.get(ticker1, ticker1)
        etf2 = ticker_name_map.get(ticker2, ticker2)

        # 2️⃣ 抓價格資料
        df1 = yf.Ticker(ticker1).history(period="3mo")
        df2 = yf.Ticker(ticker2).history(period="3mo")

        if df1.empty or df2.empty:
            raise ValueError(f"價格資料不足：{ticker1}, {ticker2}")

        # 3️⃣ 計算振幅
        for df in (df1, df2):
            df["y_close"] = df["Close"].shift(1)
            df["amplitude"] = (df["High"] - df["Low"]) / df["y_close"] * 100

        df1 = df1.reset_index()[["Date", "amplitude"]]
        df2 = df2.reset_index()[["Date", "amplitude"]]

        merged = pd.merge(df1, df2, on="Date", suffixes=("_1", "_2"))

        # 安全處理 None / NaN
        corr = merged["amplitude_1"].corr(merged["amplitude_2"])
        corr = None if corr is None or pd.isna(corr) else round(float(corr), 3)

        # 4️⃣ 傳給 template
        return render_template(
            "compare_result.html",
            etf1_code=etf1,
            etf2_code=etf2,
            amplitude_corr=corr
        )

    except Exception as e:
        print("重疊分析錯誤:", e)
        return redirect(url_for("recommend.recommend_home"))
    finally:
        db.close()


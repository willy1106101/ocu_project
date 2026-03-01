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


# @recommend_bp.route('/compare', methods=['POST'])
# def compare_etfs():
#     ticker1 = request.form.get('etf1')
#     ticker2 = request.form.get('etf2')
#     db = get_db_connection()
#     try:
#         # 1️⃣ 從資料庫抓 ETF 名稱
#         with db.cursor() as cursor:
#             sql = """
#                 SELECT ticker, ticker_yfinance, name
#                 FROM etf_tickers
#                 WHERE ticker_yfinance = %s OR ticker_yfinance = %s
#             """
#             cursor.execute(sql, (ticker1, ticker2))
#             detail_etfs = cursor.fetchall()

#         # 轉成字典方便查找名稱
#         ticker_name_map = {d['ticker_yfinance']: [d['name'],d['ticker']] for d in detail_etfs}
#         etf1 = ticker_name_map.get(ticker1, ticker1)
#         etf2 = ticker_name_map.get(ticker2, ticker2)

#         # 2️⃣ 抓價格資料
#         df1 = yf.Ticker(ticker1).history(period="3mo")
#         df2 = yf.Ticker(ticker2).history(period="3mo")

#         if df1.empty or df2.empty:
#             raise ValueError(f"價格資料不足：{ticker1}, {ticker2}")

#         # 3️⃣ 計算振幅
#         for df in (df1, df2):
#             df["y_close"] = df["Close"].shift(1)
#             df["amplitude"] = (df["High"] - df["Low"]) / df["y_close"] * 100

#         df1 = df1.reset_index()[["Date", "amplitude"]]
#         df2 = df2.reset_index()[["Date", "amplitude"]]

#         merged = pd.merge(df1, df2, on="Date", suffixes=("_1", "_2"))

#         # 安全處理 None / NaN
#         corr = merged["amplitude_1"].corr(merged["amplitude_2"])
#         corr = None if corr is None or pd.isna(corr) else round(float(corr), 3)

#         # 4️⃣ 傳給 template
#         return render_template(
#             "compare_result.html",
#             etf1_code=etf1,
#             etf2_code=etf2,
#             amplitude_corr=corr
#         )

#     except Exception as e:
#         print("重疊分析錯誤:", e)
#         return redirect(url_for("recommend.recommend_home"))
#     finally:
#         db.close()

@recommend_bp.route('/compare', methods=['POST'])
def compare_etfs():
    ticker1 = request.form.get('etf1')
    ticker2 = request.form.get('etf2')
    db = get_db_connection()
    
    def get_holdings(symbol):
        try:
            t = yf.Ticker(symbol)
            h = t.funds_data.top_holdings
            if h is not None and not h.empty:
                return {str(h.iloc[i].iloc[0]): float(h.iloc[i].iloc[1]) for i in range(len(h))}
        except: return {}
        return {}

    try:
        # 1️⃣ 抓取基本資訊與正規化後的對照表 (使用 JOIN)
        with db.cursor() as cursor:
            # 抓 ETF 名稱
            cursor.execute("SELECT ticker_yfinance, name FROM etf_tickers WHERE ticker_yfinance IN (%s, %s)", (ticker1, ticker2))
            ticker_name_map = {d['ticker_yfinance']: d['name'] for d in cursor.fetchall()}
            
            # 💡 修改點：使用 JOIN 從兩張表撈取資料
            sql_mapping = """
                SELECT m.name_en, m.name_cn, m.stock_ticker, s.sector_name 
                FROM stock_name_map m
                LEFT JOIN stock_sectors s ON m.sector_id = s.id
            """
            cursor.execute(sql_mapping)
            mapping_rows = cursor.fetchall()
            
            # 建立對照字典
            # name_lookup: {'英文名': '中文名 (代號)'}
            name_lookup = { r['name_en']: f"{r['name_cn']} ({r['stock_ticker']})" for r in mapping_rows }
            # sector_lookup: {'英文名': '產業名稱'}
            sector_lookup = { r['name_en']: r['sector_name'] for r in mapping_rows }

        # 2️⃣ 抓取成分股與計算重疊
        holdings1 = get_holdings(ticker1)
        holdings2 = get_holdings(ticker2)
        common_stocks = set(holdings1.keys()) & set(holdings2.keys())
        
        overlap_weight = 0
        overlap_details = []
        sector_summary = {}

        for stock in common_stocks:
            w1 = holdings1[stock] * 100
            w2 = holdings2[stock] * 100
            current_overlap = min(w1, w2)
            overlap_weight += current_overlap
            
            s_name = sector_lookup.get(stock, "其他")
            if s_name is None: s_name = "其他"
            
            # 取得顯示名稱 (中文+代號)
            display_name = name_lookup.get(stock, stock)

            if s_name not in sector_summary:
                sector_summary[s_name] = {'total': 0, 'stocks': []}
            
            # 累加權重並將股票加入該產業清單
            sector_summary[s_name]['total'] += current_overlap
            sector_summary[s_name]['stocks'].append(display_name)
            
            overlap_details.append({
                'name': display_name,
                'sector': s_name,
                'w1': round(w1, 2),
                'w2': round(w2, 2)
            })

        # 整理成排序後的清單
        sorted_sector_analysis = sorted(
            [
                {
                    "label": k, 
                    "value": round(v['total'], 2), 
                    "stock_list": ", ".join(v['stocks']) # 將股票清單轉成字串
                } 
                for k, v in sector_summary.items()
            ],
            key=lambda x: x['value'],
            reverse=True
        )

        # 3️⃣ 相關性計算 (維持原樣)
        df1 = yf.Ticker(ticker1).history(period="3mo")
        df2 = yf.Ticker(ticker2).history(period="3mo")
        corr = None
        if not df1.empty and not df2.empty:
            for df in (df1, df2):
                df["y_close"] = df["Close"].shift(1)
                df["amp"] = (df["High"] - df["Low"]) / df["y_close"] * 100
            merged = pd.merge(df1.reset_index(), df2.reset_index(), on="Date", suffixes=("_1", "_2"))
            if not merged.empty:
                corr = merged["amp_1"].corr(merged["amp_2"])
                corr = None if pd.isna(corr) else round(float(corr), 3)

        return render_template(
            "compare_result.html",
            etf1_name=ticker_name_map.get(ticker1, ticker1),
            etf2_name=ticker_name_map.get(ticker2, ticker2),
            amplitude_corr=corr,
            overlap_weight=round(overlap_weight, 2),
            overlap_details=overlap_details,
            sector_analysis=sorted_sector_analysis
        )

    except Exception as e:
        print("分析錯誤:", e)
        return redirect(url_for("recommend.recommend_home"))
    finally:
        db.close()
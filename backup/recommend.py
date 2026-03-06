from flask import Blueprint, render_template, request, session, redirect, url_for, make_response
from models import get_db_connection
import yfinance as yf
import pandas as pd
import csv
import io

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
            cursor.execute("SELECT t.name, t.ticker, t.ticker_yfinance, ty.name as type_name FROM etf_tickers t JOIN etf_types ty ON t.types = ty.id ORDER BY type_name ASC")
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
        # 1️⃣ 抓取基本資訊與對照表
        with db.cursor() as cursor:
            cursor.execute("SELECT ticker_yfinance, name FROM etf_tickers WHERE ticker_yfinance IN (%s, %s)", (ticker1, ticker2))
            ticker_name_map = {d['ticker_yfinance']: d['name'] for d in cursor.fetchall()}
            
            sql_mapping = """
                SELECT m.name_en, m.name_cn, m.stock_ticker, s.sector_name 
                FROM stock_name_map m
                LEFT JOIN stock_sectors s ON m.sector_id = s.id
            """
            cursor.execute(sql_mapping)
            mapping_rows = cursor.fetchall()
            name_lookup = { r['name_en']: f"{r['name_cn']} ({r['stock_ticker']})" for r in mapping_rows }
            sector_lookup = { r['name_en']: r['sector_name'] for r in mapping_rows }

        # 2️⃣ 抓取成分股與計算重疊
        holdings1 = get_holdings(ticker1)
        holdings2 = get_holdings(ticker2)
        common_stocks = set(holdings1.keys()) & set(holdings2.keys())
        
        overlap_weight = 0
        overlap_details = []
        sector_summary = {}
        overlap_intensity_score = 0

        for stock in common_stocks:
            w1 = holdings1[stock] * 100
            w2 = holdings2[stock] * 100
            current_overlap = min(w1, w2)
            overlap_weight += current_overlap

            # 計算強度：權重的平方和
            overlap_intensity_score += (current_overlap ** 2)
            
            # --- 💡 修正縮排：確保產業統計在所有情況下都執行 ---
            s_name = sector_lookup.get(stock, "其他")
            if s_name is None: s_name = "其他"
            
            display_name = name_lookup.get(stock, stock)

            if s_name not in sector_summary:
                sector_summary[s_name] = {'total': 0, 'stocks': []}
            
            sector_summary[s_name]['total'] += current_overlap
            sector_summary[s_name]['stocks'].append(display_name)
            
            overlap_details.append({
                'name': display_name,
                'sector': s_name,
                'w1': round(w1, 2),
                'w2': round(w2, 2)
            })

        # 對兩檔 ETF 進行判斷
        etf1_type = detect_etf_type(ticker_name_map.get(ticker1, ticker1), ticker1)
        etf2_type = detect_etf_type(ticker_name_map.get(ticker2, ticker2), ticker2)

        # 計算最終強度指數 (OII)
        import math
        final_intensity = round(math.sqrt(overlap_intensity_score), 2)
        
        if final_intensity > 15:
            intensity_label, intensity_color = "極高 (風險集中)", "text-danger"
        elif final_intensity > 5:
            intensity_label, intensity_color = "中等", "text-warning"
        else:
            intensity_label, intensity_color = "低 (分散良好)", "text-success"

        # 整理排序後的產業分析
        sorted_sector_analysis = sorted(
            [{"label": k, "value": round(v['total'], 2), "stock_list": ", ".join(v['stocks'])} for k, v in sector_summary.items()],
            key=lambda x: x['value'], reverse=True
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
        
        # 1️⃣ 在迴圈外部先定義好這個清單
        export_list = [] 

        for stock in common_stocks:
            w1 = holdings1[stock] * 100
            w2 = holdings2[stock] * 100
            current_overlap = min(w1, w2)
            
            # ... (原本的產業統計邏輯) ...

            # 2️⃣ 同時把資料塞進要匯出的清單
            export_list.append({
                'name': name_lookup.get(stock, stock),
                'w1': round(w1, 2),
                'w2': round(w2, 2),
                'overlap': round(current_overlap, 2)
            })
            
            # 原本的 overlap_details 也要繼續 append
            overlap_details.append({
                'name': name_lookup.get(stock, stock),
                'sector': s_name,
                'w1': round(w1, 2),
                'w2': round(w2, 2)
            })

        session['last_comparison'] = {
            'etf1_name': ticker_name_map.get(ticker1, ticker1),
            'etf2_name': ticker_name_map.get(ticker2, ticker2),
            'details': export_list
        }

        return render_template(
            "compare_result.html",
            etf1_name=ticker_name_map.get(ticker1, ticker1),
            etf2_name=ticker_name_map.get(ticker2, ticker2),
            amplitude_corr=corr,
            overlap_weight=round(overlap_weight, 2),
            overlap_details=overlap_details,
            sector_analysis=sorted_sector_analysis,
            # 💡 新增傳送給 Template 的參數
            final_intensity=final_intensity,
            intensity_label=intensity_label,
            intensity_color=intensity_color,
            etf1_type=etf1_type,
            etf2_type=etf2_type
        )

    except Exception as e:
        print("分析錯誤:", e)
        return redirect(url_for("recommend.recommend_home"))
    finally:
        db.close()


def detect_etf_type(name, ticker):
    # 1. 關鍵字判斷：主動型通常帶有「主動、動力、多空」等字眼
    active_keywords = ['主動', '動力', '多空', '絕對報酬']
    if any(k in name for k in active_keywords):
        return "主動型"
    
    # 2. 槓桿與反向型判斷 (這也是老師在意的類型)
    if '正2' in name or '槓桿' in name:
        return "槓桿型"
    if '反1' in name or '反向' in name:
        return "反向型"
    
    # 3. 預設多數為被動型 (追蹤指數型)
    return "被動型"



@recommend_bp.route('/export_comparison_excel')
def export_comparison_excel():
    # 1. 從 Session 取得剛才比對的資料
    data = session.get('last_comparison')
    
    if not data:
        return "找不到比對紀錄，請重新進行比對", 400

    si = io.StringIO()
    si.write('\ufeff')  # 解決 Excel 開啟中文亂碼
    cw = csv.writer(si)
    
    # 2. 根據兩檔 ETF 的名稱動態產生標題
    etf1 = data['etf1_name']
    etf2 = data['etf2_name']
    cw.writerow(['公司名稱', f'{etf1} 權重(%)', f'{etf2} 權重(%)', '風險重疊權重(%)'])
    
    # 3. 寫入 Session 存下來的真實細節
    for row in data['details']:
        cw.writerow([
            row['name'], 
            f"{row['w1']}%", 
            f"{row['w2']}%", 
            f"{row['overlap']}%"
        ])
        
    output = make_response(si.getvalue())
    # 設定下載檔名
    output.headers["Content-Disposition"] = f"attachment; filename=ETF_Overlap_Report.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output
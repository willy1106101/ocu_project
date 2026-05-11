from flask import Blueprint, render_template, request, session, redirect, url_for, make_response
from models import get_db_connection
from flask_caching import Cache # 💡 引入快取套件
import yfinance as yf
import pandas as pd
import csv
import io
import math

# 初始化快取 (建議放在 extensions.py，這裡為了展示先放這)
# CACHE_TYPE 使用 'SimpleCache' 即可在記憶體中運作
cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 3600})

recommend_bp = Blueprint('recommend', __name__)

# --- 💡 使用 memoize 緩存最耗時的 API 抓取功能 ---
@cache.memoize(timeout=86400) # 成分股變動頻率低，快取 24 小時
def get_holdings(symbol):
    try:
        t = yf.Ticker(symbol)
        h = t.funds_data.top_holdings
        if h is not None and not h.empty:
            return {str(h.iloc[i].iloc[0]): float(h.iloc[i].iloc[1]) for i in range(len(h))}
    except Exception as e:
        print(f"Holding抓取錯誤({symbol}): {e}")
        return {}
    return {}

@cache.memoize(timeout=3600) # 評分與行情有關，快取 1 小時
def calculate_etf_score(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        dividend = info.get("dividendYield", 0) or 0
        beta = info.get("beta", 1) or 1
        three_year = info.get("threeYearAverageReturn", 0) or 0

        score = 0
        if dividend > 0.04: score += 2
        elif dividend > 0.02: score += 1
        
        if three_year > 0.08: score += 2
        elif three_year > 0.04: score += 1
        
        if beta < 1: score += 1

        if score >= 4: return "⭐⭐⭐⭐", "優質"
        elif score >= 3: return "⭐⭐⭐", "穩健"
        elif score >= 2: return "⭐⭐", "普通"
        else: return "⭐", "觀察"
    except:
        return "⭐", "資料不足"

@recommend_bp.route('/recommend')
def recommend_home():
    user_risk = session.get('risk_level', '中風險')
    risk_map = {'低風險': (1,), '中風險': (2, 4, 10), '高風險': (3, 7, 8)}
    target_types = risk_map.get(user_risk, (2,))

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            format_strings = ','.join(['%s'] * len(target_types))
            sql = f"""
                SELECT t.name, t.ticker, t.ticker_yfinance, ty.name as type_name 
                FROM etf_tickers t
                JOIN etf_types ty ON t.types = ty.id
                WHERE t.types IN ({format_strings})
            """
            cursor.execute(sql, target_types)
            recommended_etfs = cursor.fetchall()
            
            for etf in recommended_etfs:
                stars, label = calculate_etf_score(etf['ticker_yfinance'])
                etf['score_stars'] = stars
                etf['score_label'] = label

            cursor.execute("SELECT t.name, t.ticker, t.ticker_yfinance, ty.name as type_name FROM etf_tickers t JOIN etf_types ty ON t.types = ty.id ORDER BY type_name ASC")
            all_etfs = cursor.fetchall()
            
        return render_template('recommend.html', etfs=recommended_etfs, all_etfs=all_etfs, user_risk=user_risk)
    finally:
        db.close()

@recommend_bp.route('/compare', methods=['POST'])
def compare_etfs():
    ticker1 = request.form.get('etf1')
    ticker2 = request.form.get('etf2')
    db = get_db_connection()
    
    try:
        with db.cursor() as cursor:
            # 1. 抓取基本資料與對照表
            cursor.execute("SELECT ticker_yfinance, name FROM etf_tickers WHERE ticker_yfinance IN (%s, %s)", (ticker1, ticker2))
            ticker_name_map = {d['ticker_yfinance']: d['name'] for d in cursor.fetchall()}
            
            cursor.execute("SELECT m.name_en, m.name_cn, m.stock_ticker, s.sector_name FROM stock_name_map m LEFT JOIN stock_sectors s ON m.sector_id = s.id")
            mapping_rows = cursor.fetchall()
            name_lookup = { r['name_en']: f"{r['name_cn']} ({r['stock_ticker']})" for r in mapping_rows }
            sector_lookup = { r['name_en']: r['sector_name'] for r in mapping_rows }

        # 2. 獲取成分股 (使用快取函式)
        holdings1 = get_holdings(ticker1)
        holdings2 = get_holdings(ticker2)
        common_stocks = set(holdings1.keys()) & set(holdings2.keys())
        
        overlap_weight = 0
        overlap_details = []
        export_list = [] # 💡 合併 export 與顯示清單，減少迴圈次數
        sector_summary = {}
        overlap_intensity_score = 0

        for stock in common_stocks:
            w1 = holdings1[stock] * 100
            w2 = holdings2[stock] * 100
            current_overlap = min(w1, w2)
            overlap_weight += current_overlap
            overlap_intensity_score += (current_overlap ** 2)
            
            s_name = sector_lookup.get(stock, "其他") or "其他"
            display_name = name_lookup.get(stock, stock)

            item = {
                'name': display_name,
                'sector': s_name,
                'w1': round(w1, 2),
                'w2': round(w2, 2),
                'overlap': round(current_overlap, 2)
            }
            overlap_details.append(item)
            export_list.append(item)

            if s_name not in sector_summary:
                sector_summary[s_name] = {'total': 0, 'stocks': []}
            sector_summary[s_name]['total'] += current_overlap
            sector_summary[s_name]['stocks'].append(display_name)

        # 3. 計算 OII 指數與類型標籤
        final_intensity = round(math.sqrt(overlap_intensity_score), 2)
        if final_intensity > 15: intensity_label, intensity_color = "極高 (風險集中)", "text-danger"
        elif final_intensity > 5: intensity_label, intensity_color = "中等", "text-warning"
        else: intensity_label, intensity_color = "低 (分散良好)", "text-success"

        etf1_type = detect_etf_type(ticker_name_map.get(ticker1, ticker1), ticker1)
        etf2_type = detect_etf_type(ticker_name_map.get(ticker2, ticker2), ticker2)

        # 4. 相關性計算 (使用快取優化效能)
        corr = calculate_correlation(ticker1, ticker2)

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
            sector_analysis=sorted([{"label": k, "value": round(v['total'], 2), "stock_list": ", ".join(v['stocks'])} for k, v in sector_summary.items()], key=lambda x: x['value'], reverse=True),
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

@cache.memoize(timeout=3600)
def calculate_correlation(t1, t2):
    try:
        df1 = yf.Ticker(t1).history(period="3mo")
        df2 = yf.Ticker(t2).history(period="3mo")
        if not df1.empty and not df2.empty:
            for df in (df1, df2):
                df["y_close"] = df["Close"].shift(1)
                df["amp"] = (df["High"] - df["Low"]) / df["y_close"] * 100
            merged = pd.merge(df1.reset_index(), df2.reset_index(), on="Date", suffixes=("_1", "_2"))
            if not merged.empty:
                corr = merged["amp_1"].corr(merged["amp_2"])
                return round(float(corr), 3) if not pd.isna(corr) else None
    except: return None
    return None

def detect_etf_type(name, ticker):
    if any(k in name for k in ['主動', '動力', '多空']): return "主動型"
    if '正2' in name or '槓桿' in name: return "槓桿型"
    if '反1' in name or '反向' in name: return "反向型"
    return "被動型"

@recommend_bp.route('/export_comparison_excel')
def export_comparison_excel():
    data = session.get('last_comparison')
    if not data: return "無比對紀錄", 400
    si = io.StringIO()
    si.write('\ufeff')
    cw = csv.writer(si)
    cw.writerow(['公司名稱', f"{data['etf1_name']} 權重(%)", f"{data['etf2_name']} 權重(%)", '風險重疊權重(%)'])
    for row in data['details']:
        cw.writerow([row['name'], f"{row['w1']}%", f"{row['w2']}%", f"{row['overlap']}%"])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=ETF_Overlap_Report.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output
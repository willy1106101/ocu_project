from flask import Blueprint, render_template, request, session, redirect, url_for, make_response
from models import get_db_connection
from flask_caching import Cache
import yfinance as yf
import pandas as pd
import csv
import io
import math

cache = Cache(config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 3600})
recommend_bp = Blueprint('recommend', __name__)

# --- 💡 高效快取函式區 ---
@cache.memoize(timeout=86400)
def get_holdings(symbol):
    try:
        t = yf.Ticker(symbol)
        h = t.funds_data.top_holdings
        return {str(h.iloc[i].iloc[0]): float(h.iloc[i].iloc[1]) for i in range(len(h))} if h is not None else {}
    except: return {}

@cache.memoize(timeout=3600)
def calculate_etf_score(ticker):
    try:
        info = yf.Ticker(ticker).info
        score = (2 if info.get("dividendYield", 0) > 0.04 else (1 if info.get("dividendYield", 0) > 0.02 else 0)) + \
                (2 if info.get("threeYearAverageReturn", 0) > 0.08 else (1 if info.get("threeYearAverageReturn", 0) > 0.04 else 0)) + \
                (1 if info.get("beta", 1) < 1 else 0)
        stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"][min(score, 4)]
        return stars, ["觀察", "普通", "穩健", "優質", "優質"][min(score, 4)]
    except: return "⭐", "資料不足"

@cache.memoize(timeout=3600)
def calculate_correlation(t1, t2):
    try:
        df1, df2 = yf.Ticker(t1).history(period="3mo"), yf.Ticker(t2).history(period="3mo")
        if df1.empty or df2.empty: return None
        for df in (df1, df2):
            df["y_close"] = df["Close"].shift(1)
            df["amp"] = (df["High"] - df["Low"]) / df["y_close"] * 100
        merged = pd.merge(df1.reset_index(), df2.reset_index(), on="Date", suffixes=("_1", "_2"))
        corr = merged["amp_1"].corr(merged["amp_2"])
        return round(float(corr), 3) if not pd.isna(corr) else None
    except: return None

# --- 路由區 ---
@recommend_bp.route('/recommend')
def recommend_home():
    user_risk = session.get('risk_level', '中風險')
    risk_map = {'低風險': (1,), '中風險': (2, 4, 10), '高風險': (3, 7, 8)}
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute(f"SELECT t.name, t.ticker, t.ticker_yfinance, ty.name as type_name FROM etf_tickers t JOIN etf_types ty ON t.types = ty.id WHERE t.types IN ({','.join(['%s']*len(risk_map.get(user_risk, (2,))) )})", risk_map.get(user_risk, (2,)))
            etfs = cursor.fetchall()
            for e in etfs: e['score_stars'], e['score_label'] = calculate_etf_score(e['ticker_yfinance'])
            cursor.execute("SELECT t.name, t.ticker, t.ticker_yfinance, ty.name as type_name FROM etf_tickers t JOIN etf_types ty ON t.types = ty.id ORDER BY type_name ASC")
            return render_template('recommend.html', etfs=etfs, all_etfs=cursor.fetchall(), user_risk=user_risk)
    finally: db.close()

@recommend_bp.route('/compare', methods=['POST'])
def compare_etfs():
    ticker1, ticker2 = request.form.get('etf1'), request.form.get('etf2')
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT ticker_yfinance, name FROM etf_tickers WHERE ticker_yfinance IN (%s, %s)", (ticker1, ticker2))
            names = {d['ticker_yfinance']: d['name'] for d in cursor.fetchall()}
            cursor.execute("SELECT name_en, name_cn, stock_ticker, sector_name FROM stock_name_map m LEFT JOIN stock_sectors s ON m.sector_id = s.id")
            mapping = {r['name_en']: {'display': f"{r['name_cn']} ({r['stock_ticker']})", 'sector': r['sector_name'] or "其他"} for r in cursor.fetchall()}

        h1, h2 = get_holdings(ticker1), get_holdings(ticker2)
        common = set(h1.keys()) & set(h2.keys())
        details, sector_sum, oii_sq, total_w = [], {}, 0, 0
        for s in common:
            w1, w2 = h1[s]*100, h2[s]*100
            overlap = min(w1, w2)
            total_w += overlap
            oii_sq += (overlap**2)
            meta = mapping.get(s, {'display': s, 'sector': '其他'})
            details.append({'name': meta['display'], 'sector': meta['sector'], 'w1': round(w1,2), 'w2': round(w2,2), 'overlap': round(overlap,2)})
            sector_sum[meta['sector']] = sector_sum.get(meta['sector'], 0) + overlap
            
        final_oii = round(math.sqrt(oii_sq), 2)
        session['last_comparison'] = {'etf1_name': names.get(ticker1, ticker1), 'etf2_name': names.get(ticker2, ticker2), 'details': details}
        
        return render_template("compare_result.html", 
                               etf1_name=names.get(ticker1, ticker1), etf2_name=names.get(ticker2, ticker2),
                               amplitude_corr=calculate_correlation(ticker1, ticker2),
                               overlap_weight=round(total_w, 2), overlap_details=details,
                               sector_analysis=sorted([{'label': k, 'value': round(v,2)} for k, v in sector_sum.items()], key=lambda x: x['value'], reverse=True),
                               final_intensity=final_oii, 
                               intensity_label="極高" if final_oii>15 else ("中等" if final_oii>5 else "低"),
                               intensity_color="text-danger" if final_oii>15 else ("text-warning" if final_oii>5 else "text-success"))
    finally: db.close()

@recommend_bp.route('/export_comparison_excel')
def export_comparison_excel():
    data = session.get('last_comparison')
    if not data: return "無比對紀錄", 400
    si = io.StringIO()
    si.write('\ufeff')
    cw = csv.writer(si)
    cw.writerow(['公司名稱', f"{data['etf1_name']} 權重(%)", f"{data['etf2_name']} 權重(%)", '風險重疊權重(%)'])
    for r in data['details']: cw.writerow([r['name'], f"{r['w1']}%", f"{r['w2']}%", f"{r['overlap']}%"])
    output = make_response(si.getvalue())
    output.headers.update({"Content-Disposition": "attachment; filename=ETF_Overlap_Report.csv", "Content-type": "text/csv; charset=utf-8"})
    return output
from flask import Blueprint, render_template, request, session, redirect, url_for
from models import get_db_connection

recommend_bp = Blueprint('recommend', __name__)

@recommend_bp.route('/recommend')
def recommend_home():
    user_risk = session.get('risk_level', '中風險')
    
    # 定義類型的邏輯對應
    risk_map = {
        '低風險': (1,), 
        '中風險': (2, 4, 10), 
        '高風險': (3, 7, 8)
    }
    target_types = risk_map.get(user_risk, (2,))

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 1. 抓取符合該風險類型的 ETF
            format_strings = ','.join(['%s'] * len(target_types))
            sql = f"SELECT name, ticker FROM etf_tickers WHERE types IN ({format_strings}) LIMIT 6"
            cursor.execute(sql, target_types)
            recommended_etfs = cursor.fetchall()
            
            # 2. 抓取「所有」ETF 供比對下拉選單使用 (這會顯示 300 多檔)
            cursor.execute("SELECT ticker, name FROM etf_tickers ORDER BY ticker ASC")
            all_etfs = cursor.fetchall()
            
        return render_template('recommend.html', 
                               etfs=recommended_etfs, 
                               all_etfs=all_etfs, 
                               user_risk=user_risk)
    finally:
        db.close()

@recommend_bp.route('/compare', methods=['POST'])
def compare_etfs():
    etf1 = request.form.get('etf1')
    etf2 = request.form.get('etf2')
    
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 找出兩檔 ETF 的共同成分股
            sql = """
                SELECT a.stock_code, a.stock_name, a.weight as w1, b.weight as w2
                FROM etf_composition a
                JOIN etf_composition b ON a.stock_code = b.stock_code
                WHERE a.etf_code = %s AND b.etf_code = %s
            """
            cursor.execute(sql, (etf1, etf2))
            overlap_stocks = cursor.fetchall()
            
            # 計算平均重疊權重 (這只是簡單指標)
            total_overlap = sum([(s['w1'] + s['w2']) / 2 for s in overlap_stocks])
            
        return render_template('compare_result.html', 
                               stocks=overlap_stocks, 
                               etf1=etf1, etf2=etf2, 
                               total_overlap=total_overlap)
    finally:
        db.close()
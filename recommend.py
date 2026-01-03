from flask import Blueprint, render_template, request, session, redirect, url_for
from models import get_db_connection

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
                SELECT t.name, t.ticker, ty.name as type_name 
                FROM etf_tickers t
                JOIN etf_types ty ON t.types = ty.id
                WHERE t.types IN ({format_strings}) 
                LIMIT 6
            """
            cursor.execute(sql, target_types)
            recommended_etfs = cursor.fetchall()
            
            # 抓取所有 ETF 供下拉選單
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
    
    # 如果使用者沒選就按分析，導回原頁面
    if not etf1 or not etf2:
        return redirect(url_for('recommend.recommend_home'))

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 加入 COLLATE 防止編碼錯誤 1267
            sql = """
                SELECT a.stock_code, a.stock_name, a.weight as w1, b.weight as w2
                FROM etf_composition a
                JOIN etf_composition b ON a.stock_code COLLATE utf8mb4_unicode_ci = b.stock_code COLLATE utf8mb4_unicode_ci
                WHERE a.etf_code = %s AND b.etf_code = %s
            """
            cursor.execute(sql, (etf1, etf2))
            overlap_stocks = cursor.fetchall()
            
            # 專業計算方式：取兩者權重的最小值並加總
            # 例如：A 持有台積電 50%，B 持有 30%，則兩者重疊度為 30%
            total_overlap = sum([min(s['w1'], s['w2']) for s in overlap_stocks])
            total_overlap = round(total_overlap, 2)
            
        return render_template('compare_result.html', 
                               stocks=overlap_stocks, 
                               etf1=etf1, etf2=etf2, 
                               total_overlap=total_overlap)
    finally:
        db.close()
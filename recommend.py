from flask import Blueprint, render_template, request, session, redirect, url_for
from models import get_db_connection

recommend_bp = Blueprint('recommend', __name__)

@recommend_bp.route('/recommend')
def recommend_home():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # 取得使用者目前的風險等級 (預設為中風險)
    user_risk = session.get('risk_level', '中風險')
    
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 1. 根據風險等級推薦 ETF
            sql = "SELECT * FROM etf_list WHERE risk_level = %s"
            cursor.execute(sql, (user_risk,))
            recommended_etfs = cursor.fetchall()
            
            # 2. 獲取所有 ETF 清單供重複性比對下拉選單使用
            cursor.execute("SELECT etf_code, name FROM etf_list")
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
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import get_db_connection

portfolio_bp = Blueprint('portfolio', __name__)

# --- 顯示已持有股票清單 ---
@portfolio_bp.route('/list')
def list_stocks():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 抓取該使用者的持股資料
            sql = "SELECT * FROM user_portfolio WHERE user_id = %s"
            cursor.execute(sql, (session['user_id'],))
            my_stocks = cursor.fetchall()
        return render_template('portfolio_list.html', stocks=my_stocks)
    finally:
        db.close()

# --- 新增股票資料 ---
@portfolio_bp.route('/add', methods=['POST'])
def add_stock():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    # 取得表單數據 (對應你要求的欄位)
    data = (
        session['user_id'],
        request.form.get('stock_name'),
        request.form.get('stock_code'),
        request.form.get('buy_price'),      # 買入均價
        request.form.get('dividend'),       # 除息金額
        request.form.get('current_price'),  # 目前價格
        request.form.get('buy_date')        # 成交日期
    )

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            sql = """INSERT INTO user_portfolio 
                     (user_id, stock_name, stock_code, buy_price, dividend, current_price, buy_date) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql, data)
        db.commit()
        flash('股票新增成功！', 'success')
    finally:
        db.close()
    return redirect(url_for('portfolio.list_stocks'))

# --- 刪除股票資料 ---
@portfolio_bp.route('/delete/<int:id>')
def delete_stock(id):
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM user_portfolio WHERE id = %s AND user_id = %s", (id, session['user_id']))
        db.commit()
        flash('資料已刪除', 'info')
    finally:
        db.close()
    return redirect(url_for('portfolio.list_stocks'))
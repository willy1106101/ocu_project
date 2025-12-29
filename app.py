from flask import Flask, redirect, url_for, render_template, session
from auth import auth_bp
from profolio import portfolio_bp
from recommend import recommend_bp
from models import get_db_connection

app = Flask(__name__)
app.secret_key = 'your_key'

# 註冊藍圖
app.register_blueprint(auth_bp, url_prefix='/auth')
# 股票管理模組
app.register_blueprint(portfolio_bp, url_prefix='/portfolio')
# 推薦系統模組 
app.register_blueprint(recommend_bp, url_prefix='/recommend')

@app.route('/')
def index():
    # 轉跳到 '/auth/login' 讓使用者登入
    return redirect(url_for('auth.login'))

@app.route('/index')
def home():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 1. 抓取前 3 筆熱門股票 (首頁行情)
            cursor.execute("SELECT * FROM etf_list LIMIT 3")
            top_stocks = cursor.fetchall()
            
            # 2. 抓取漲幅排序 (這裡假設按報酬率排)
            cursor.execute("SELECT name, annual_return FROM etf_list ORDER BY annual_return DESC LIMIT 5")
            rank_list = cursor.fetchall()
            
        return render_template('index.html', 
                               stocks=top_stocks, 
                               rank_list=rank_list, 
                               username=session.get('username'))
    finally:
        db.close()

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, redirect, url_for, render_template, session
import yfinance as yf
from auth import auth_bp
from portfolio import portfolio_bp
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
    user_id = session.get('user_id')
    try:
        with db.cursor() as cursor:
            # --- 1. 抓取首頁焦點 ETF (yfinance 即時行情) ---
            sql_tickers = "SELECT name, ticker, ticker_yfinance FROM etf_tickers ORDER BY rand() DESC LIMIT 5"
            cursor.execute(sql_tickers)
            tickers = cursor.fetchall()
            
            real_data = []
            for item in tickers:
                info = get_realtime_etf(item['ticker_yfinance'])
                if info:
                    real_data.append({
                        'name': item['name'],
                        'code': item['ticker'],
                        'price': info['current_price'],
                        'change': info['change_percent'],
                        'open': info['open_price'],
                        'annual_return': info['change_percent'] # 對應 index.html 報錯處
                    })
            
            rank_list = sorted(real_data, key=lambda x: x['annual_return'], reverse=True)

            # --- 1. 抓取該使用者的持股 (從 user_portfolio) ---
            # 這裡我們抓取該使用者買過的所有不重複代號
            sql_my_stocks = """
                SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance 
                FROM user_portfolio p
                JOIN etf_tickers t ON p.stock_code = t.ticker
                WHERE p.user_id = %s
            """
            cursor.execute(sql_my_stocks, (user_id,))
            my_tickers = cursor.fetchall()

            my_portfolio_data = []
            for item in my_tickers:
                info = get_realtime_etf(item['ticker_yfinance'])
                if info:
                    my_portfolio_data.append({
                        'name': item['stock_name'],
                        'code': item['stock_code'],
                        'price': info['current_price'],
                        'change': info['change_percent'],
                        'open': info['open_price'],
                        'annual_return': info['change_percent'] # 對應 index.html 報錯處
                    })
    except Exception as e:
        print(f"資料讀取錯誤: {e}")
    finally:
        db.close()
    
    # 確保傳入 stocks 和 rank_list
    return render_template('index.html', 
                           stocks=real_data, 
                           rank_list=rank_list, 
                           username=session.get('username'),
                           my_stocks=my_portfolio_data)


def get_realtime_etf(ticker_yfinance):
    """
    輸入 yfinance 格式的代號 (例如: 0050.TW)
    回傳該 ETF 的即時行情字典
    """
    try:
        # 建立 yfinance 物件
        yt = yf.Ticker(ticker_yfinance)
        
        # 抓取最近兩天的歷史資料來計算漲跌
        hist = yt.history(period="2d")
        
        if hist.empty:
            return None
            
        # 取得最新一筆與前一筆的資料
        latest_data = hist.iloc[-1]
        prev_close = hist['Close'].iloc[0]
        
        current_price = latest_data['Close']
        open_price = latest_data['Open']
        
        # 計算漲跌幅
        change = current_price - prev_close
        change_percent = (change / prev_close) * 100
        
        return {
            'current_price': round(current_price, 2),
            'change_percent': round(change_percent, 2),
            'open_price': round(open_price, 2)
        }
    except Exception as e:
        print(f"抓取資料發生錯誤 ({ticker_yfinance}): {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True)
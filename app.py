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
    
    # 預先初始化變數
    real_data = []
    my_portfolio_data = []
    rank_list = []
    
    try:
        with db.cursor() as cursor:
            # 1. 抓取隨機焦點 ETF
            sql_tickers = "SELECT name, ticker, ticker_yfinance FROM etf_tickers ORDER BY rand() LIMIT 5"
            cursor.execute(sql_tickers)
            tickers = cursor.fetchall()
            
            for item in tickers:
                info = get_realtime_etf(item['ticker_yfinance'])
                # 計算真實績效
                perf = get_etf_performance(item['ticker_yfinance']) 
                
                # 即使 info 為 None，也要填入預設值，防止前端報錯
                real_data.append({
                    'name': item['name'],
                    'code': item['ticker'],
                    'price': info['current_price'] if info else 0.0,
                    'change': info['change_percent'] if info else 0.0,
                    'open': info['open_price'] if info else 0.0,
                    'annual_return': perf if perf else 0.0  # 確保 Key 一定存在
                })
            
            # 排序生成排行榜
            rank_list = sorted(real_data, key=lambda x: x['annual_return'], reverse=True)

            # 2. 抓取個人持股 (加上 COLLATE 解決編碼問題)
            sql_my_stocks = """
                SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance 
                FROM user_portfolio p
                JOIN etf_tickers t ON p.stock_code COLLATE utf8mb4_unicode_ci = t.ticker COLLATE utf8mb4_unicode_ci
                WHERE p.user_id = %s
            """
            cursor.execute(sql_my_stocks, (user_id,))
            my_tickers = cursor.fetchall()

            for item in my_tickers:
                info = get_realtime_etf(item['ticker_yfinance'])
                perf = get_etf_performance(item['ticker_yfinance']) 
                if info:
                    my_portfolio_data.append({
                        'name': item['stock_name'],
                        'code': item['stock_code'],
                        'open': info['open_price'],
                        'price': info['current_price'],
                        'change': info['change_percent'],
                        'annual_return': perf if perf else 0.0  # 確保 Key 一定存在
                    })
                    
    except Exception as e:
        print(f"資料讀取錯誤: {e}")
    finally:
        db.close()
    
    return render_template('index.html', 
                           stocks=real_data, 
                           rank_list=rank_list, 
                           my_stocks=my_portfolio_data,
                           username=session.get('username'))


def get_etf_performance(ticker_yfinance):
    try:
        etf = yf.Ticker(ticker_yfinance)
        hist = etf.history(period="1y")
        
        if hist.empty or len(hist) < 20: # 確保有足夠的交易天數
            return 0.0
            
        # 使用第 0 筆與最後一筆資料
        # 因為 auto_adjust=True，這裡的 Close 其實就是總報酬價格
        start_price = hist['Close'].iloc[0]
        end_price = hist['Close'].iloc[-1]
        
        if start_price == 0: return 0.0
        
        # 真正的總報酬率 (Total Return)
        total_return = ((end_price - start_price) / start_price) * 100
        
        return round(total_return, 2)
    except Exception as e:
        print(f"抓取績效失敗 ({ticker_yfinance}): {e}")
        return 0.0

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
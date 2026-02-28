from flask import Flask, redirect, url_for, render_template, session
import yfinance as yf
import datetime
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
    
    real_data = []
    my_portfolio_data = []
    rank_list = []
    
    try:
        with db.cursor() as cursor:

            # ========= 1️⃣ 隨機焦點 ETF =========
            sql_tickers = """
                SELECT name, ticker, ticker_yfinance 
                FROM etf_tickers 
                ORDER BY rand() 
                LIMIT 5
            """
            cursor.execute(sql_tickers)
            tickers = cursor.fetchall()

            for item in tickers:
                info = get_etf_snapshot(item['ticker_yfinance'])

                real_data.append({
                    'name': item['name'],
                    'code': item['ticker'],
                    'price': info['price'] if info else 0.0,
                    'change': info['change'] if info else 0.0,
                    'open': info['open'] if info else 0.0,
                    'last_close': info['last_close'] if info else 0.0,
                    'annual_return': info['annual_return'] if info else 0.0
                })

            # 排序產生排行榜
            rank_list = sorted(
                real_data,
                key=lambda x: x['annual_return'],
                reverse=True
            )

            # ========= 2️⃣ 個人持股 =========
            sql_my_stocks = """
                SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance 
                FROM user_portfolio p
                JOIN etf_tickers t 
                  ON p.stock_code COLLATE utf8mb4_unicode_ci 
                   = t.ticker COLLATE utf8mb4_unicode_ci
                WHERE p.user_id = %s
            """
            cursor.execute(sql_my_stocks, (user_id,))
            my_tickers = cursor.fetchall()

            for item in my_tickers:
                info = get_etf_snapshot(item['ticker_yfinance'])

                if info:
                    my_portfolio_data.append({
                        'name': item['stock_name'],
                        'code': item['stock_code'],
                        'open': info['open'],
                        'price': info['price'],
                        'change': info['change'],
                        'last_close': info['last_close'],
                        'amp': info['amp'],
                        'annual_return': info['annual_return']
                    })

    except Exception as e:
        print(f"資料讀取錯誤: {e}")

    finally:
        db.close()

    return render_template(
        'index.html',
        stocks=real_data,
        rank_list=rank_list,
        my_stocks=my_portfolio_data,
        username=session.get('username')
    )

def get_etf_snapshot(ticker_yfinance):
    try:
        ticker = yf.Ticker(ticker_yfinance)

        hist_1y = ticker.history(period="1y")
        hist_5d = ticker.history(period="5d")

        if hist_5d.empty:
            return None

        # ==== 即時價格 ====
        latest = hist_5d.iloc[-1]
        prev = hist_5d.iloc[-2] if len(hist_5d) >= 2 else latest

        current_price = latest["Close"]
        open_price = latest["Open"]
        yesterday_close = prev["Close"]

        change_percent = ((current_price - yesterday_close) / yesterday_close) * 100

        # ==== 振幅 ====
        amplitude = ((latest["High"] - latest["Low"]) / yesterday_close) * 100

        # ==== 年報酬 ====
        if not hist_1y.empty:
            price_col = "Adj Close" if "Adj Close" in hist_1y.columns else "Close"
            start_price = hist_1y[price_col].iloc[0]
            end_price = hist_1y[price_col].iloc[-1]
            annual_return = ((end_price - start_price) / start_price) * 100
        else:
            annual_return = 0

        return {
            "price": round(current_price, 2),
            "change": round(change_percent, 2),
            "open": round(open_price, 2),
            "last_close": round(yesterday_close, 2),
            "amp": round(amplitude, 2),
            "annual_return": round(annual_return, 2)
        }

    except Exception as e:
        print(ticker_yfinance, e)
        return None


def get_amplitude(ticker_yfinance):
    try:
        ticker = yf.Ticker(ticker_yfinance)

        # 抓最近 5 天，避免假日
        hist = ticker.history(period="5d")

        if hist.empty or len(hist) < 2:
            return None

        # 今日資料
        today = hist.iloc[-1]

        # 昨收價（前一交易日）
        yesterday_close = hist["Close"].iloc[-2]

        high_price = today["High"]
        low_price = today["Low"]

        amplitude = (high_price - low_price) / yesterday_close * 100

        return round(float(amplitude), 2)

    except Exception as e:
        print(f"{ticker_yfinance} error:", e)
        return None

def get_exact_performance(ticker_yfinance):
    try:
        etf = yf.Ticker(ticker_yfinance)
        hist = etf.history(period="1y")

        if hist.empty:
            return None

        # 台股 ETF 通常沒有 Adj Close
        price_col = "Adj Close" if "Adj Close" in hist.columns else "Close"

        start_price = hist[price_col].iloc[0]
        end_price = hist[price_col].iloc[-1]
        print(start_price,end_price)

        return round(((end_price - start_price) / start_price)* 100, 2)

    except Exception as e:
        print(f"{ticker_yfinance} error:", e)
        return None



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


def get_yesterday_close(ticker_yfinance):
    try:
        ticker = yf.Ticker(ticker_yfinance)

        # 抓最近 5 天，避免遇到假日
        hist = ticker.history(period="5d")

        if hist.empty or len(hist) < 2:
            return None

        # 昨收 = 倒數第 2 個交易日的 Close
        yesterday_close = hist["Close"].iloc[-2]

        return round(float(yesterday_close), 2)

    except Exception as e:
        print(f"{ticker_yfinance} error:", e)
        return None

if __name__ == '__main__':
    app.run(debug=True)
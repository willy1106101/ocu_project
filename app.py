from flask import Flask, redirect, url_for, render_template, session
import yfinance as yf
from datetime import datetime, timedelta
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
    # 💡 新增：儲存總產業分佈的字典
    all_sector_dist = {}
    
    try:
        with db.cursor() as cursor:
            # --- 1. 抓取成分股與產業的對照字典 ---
            sql_mapping = """
                SELECT m.name_en, s.sector_name 
                FROM stock_name_map m
                LEFT JOIN stock_sectors s ON m.sector_id = s.id
            """
            cursor.execute(sql_mapping)
            # 建立字典: {'英文名稱': '產業名稱'}
            sector_lookup = {r['name_en']: r['sector_name'] for r in cursor.fetchall()}

            # --- 2. 隨機焦點 ETF (維持原樣) ---
            sql_tickers = "SELECT name, ticker, ticker_yfinance FROM etf_tickers ORDER BY rand() LIMIT 5"
            cursor.execute(sql_tickers)
            tickers = cursor.fetchall()
            for item in tickers:
                info = get_etf_snapshot(item['ticker_yfinance'])
                price_pos = get_price_position(item['ticker_yfinance'])
                if info:
                    real_data.append({
                        'name': item['name'], 'code': item['ticker'], 'price': info['price'],
                        'change': info['change'], 'open': info['open'], 'last_close': info['last_close'],
                        'annual_return': info['annual_return'],
                        'pos': price_pos  # 優先使用 get_price_position 的結果
                    })
            rank_list = sorted(real_data, key=lambda x: x['annual_return'], reverse=True)

            # --- 3. 個人持股與產業統計 ---
            sql_my_stocks = """
                SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance 
                FROM user_portfolio p
                JOIN etf_tickers t ON p.stock_code = t.ticker
                WHERE p.user_id = %s
            """
            cursor.execute(sql_my_stocks, (user_id,))
            my_tickers = cursor.fetchall()

            for item in my_tickers:
                info = get_etf_snapshot(item['ticker_yfinance'])
                price_pos = get_price_position(item['ticker_yfinance'])
                if info:
                    my_portfolio_data.append({
                        'name': item['stock_name'], 'code': item['stock_code'], 'price': info['price'],
                        'change': info['change'], 'annual_return': info['annual_return'], 'amp': info['amp'],
                        'pos': price_pos  # 優先使用 get_price_position 的結果
                    })
                    
                    # 💡 關鍵：統計該 ETF 的產業分佈
                    try:
                        t = yf.Ticker(item['ticker_yfinance'])
                        holdings = t.funds_data.top_holdings
                        if holdings is not None and not holdings.empty:
                            for i in range(len(holdings)):
                                stock_en = str(holdings.iloc[i].iloc[0])
                                weight = float(holdings.iloc[i].iloc[1]) * 100
                                s_name = sector_lookup.get(stock_en, "其他")
                                # 加總到全資產產業分佈
                                all_sector_dist[s_name] = all_sector_dist.get(s_name, 0) + weight
                    except: continue

        # 整理產業資料給 Chart.js
        dashboard_sector_analysis = sorted(
            [{"label": k, "value": round(v, 2)} for k, v in all_sector_dist.items()],
            key=lambda x: x['value'], reverse=True
        )

        print("--- [資料校對報告] ---")
        for s in my_portfolio_data:
            print(f"標的: {s['code']}, 價格: {s['price']}, 位階: {s['pos']}")
            
        total_sector_weight = sum(item['value'] for item in dashboard_sector_analysis)
        print(f"總產業權重加總: {total_sector_weight}% (應接近 100%)")
        print("--------------------")

    except Exception as e:
        print(f"資料讀取錯誤: {e}")
        dashboard_sector_analysis = []
    finally:
        db.close()

    return render_template(
        'index.html',
        stocks=real_data,
        rank_list=rank_list,
        my_stocks=my_portfolio_data,
        username=session.get('username'),
        # 💡 傳送到前端
        dashboard_sector_analysis=dashboard_sector_analysis,
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

def get_price_position(ticker_yfinance):
    try:
        ticker = yf.Ticker(ticker_yfinance)
        # 抓取 1 個月資料
        hist = ticker.history(period="1mo") 
        if len(hist) < 2: return None

        current_price = hist['Close'].iloc[-1]
        
        # 💡 關鍵修正：排除最後一筆(今天)，計算過去的區間
        past_hist_7d = hist.iloc[:-1].tail(7)
        past_hist_30d = hist.iloc[:-1]

        # 取得過去的極值
        max_7 = past_hist_7d['High'].max()
        min_7 = past_hist_7d['Low'].min()
        max_30 = past_hist_30d['High'].max()
        min_30 = past_hist_30d['Low'].min()

        # 💡 增加容許區間 (例如 1% 內就算高檔)
        threshold = 1.01 # 高於過去最高點或在 1% 誤差內

        return {
            'current': round(current_price, 2),
            # 只要今天收盤價「接近」或「超過」過去最高，就亮燈
            'is_7d_high': current_price >= max_7 * 0.99,
            'is_7d_low': current_price <= min_7 * 1.01,
            'is_30d_high': current_price >= max_30 * 0.99,
            'is_30d_low': current_price <= min_30 * 1.01,
        }
    except Exception as e:
        print(f"位階計算錯誤: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True)
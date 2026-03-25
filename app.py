from flask import Flask, redirect, url_for, render_template, session
import yfinance as yf
from datetime import datetime, timedelta
import datetime
from service.auth import auth_bp
from service.portfolio import portfolio_bp
from service.recommend import recommend_bp
from service.models import get_db_connection

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


# --- 核心工具函數：一次抓取所有需要的行情與位階數據 ---
def get_full_etf_data(ticker_yfinance):
    try:
        ticker = yf.Ticker(ticker_yfinance)
        # 一次抓取 3 個月資料，涵蓋月、季、7日的運算需求
        hist_3m = ticker.history(period="3mo")
        if hist_3m.empty or len(hist_3m) < 2:
            return None

        # 1. 基礎行情 (今日與昨收)
        latest = hist_3m.iloc[-1]
        prev = hist_3m.iloc[-2]
        current_price = latest["Close"]
        yesterday_close = prev["Close"]
        
        # 2. 漲跌幅與振幅
        change_percent = ((current_price - yesterday_close) / yesterday_close) * 100
        amplitude = ((latest["High"] - latest["Low"]) / yesterday_close) * 100

        # 3. 年報酬 (從 1年資料抓取，若為了效能可改用 3個月模擬或另外抓)
        hist_1y = ticker.history(period="1y")
        annual_return = 0
        if not hist_1y.empty:
            start_p = hist_1y["Close"].iloc[0]
            end_p = hist_1y["Close"].iloc[-1]
            annual_return = ((end_p - start_p) / start_p) * 100

        # 4. 位階計算 (排除今日後的過去區間)
        past_3m = hist_3m.iloc[:-1]
        past_1m = past_3m.tail(20) # 約一個月交易日
        past_7d = past_3m.tail(7)

        # 取得各區間極值
        max_7, min_7 = past_7d['High'].max(), past_7d['Low'].min()
        max_30, min_30 = past_1m['High'].max(), past_1m['Low'].min()
        max_90, min_90 = past_3m['High'].max(), past_3m['Low'].min()

        return {
            "price": round(current_price, 2),
            "change": round(change_percent, 2),
            "last_close": round(yesterday_close, 2),
            "amp": round(amplitude, 2),
            "annual_return": round(annual_return, 2),
            # 位階標籤 (使用 1% 容許區間)
            "pos": {
                "is_7d_high": current_price >= max_7 * 0.99,
                "is_7d_low": current_price <= min_7 * 1.01,
                "is_30d_high": current_price >= max_30 * 0.99,
                "is_30d_low": current_price <= min_30 * 1.01,
                "is_90d_high": current_price >= max_90 * 0.99,
                "is_90d_low": current_price <= min_90 * 1.01,
            },
            # 高低價數值
            "month_high": round(max_30, 2), "month_low": round(min_30, 2),
            "quarter_high": round(max_90, 2), "quarter_low": round(min_90, 2)
        }
    except Exception as e:
        print(f"數據抓取失敗({ticker_yfinance}): {e}")
        return None

# --- 主頁面路由 ---
@app.route('/index')
def home():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    db = get_db_connection()
    user_id = session.get('user_id')
    real_data, my_portfolio_data, all_sector_dist = [], [], {}
    
    try:
        with db.cursor() as cursor:
            # 1. 產業對照表
            cursor.execute("SELECT m.name_en, s.sector_name FROM stock_name_map m LEFT JOIN stock_sectors s ON m.sector_id = s.id")
            sector_lookup = {r['name_en']: r['sector_name'] for r in cursor.fetchall()}

            # 2. 市場焦點 ETF
            cursor.execute("SELECT name, ticker, ticker_yfinance FROM etf_tickers ORDER BY rand() LIMIT 5")
            for item in cursor.fetchall():
                full_info = get_full_etf_data(item['ticker_yfinance'])
                if full_info:
                    full_info.update({'name': item['name'], 'code': item['ticker']})
                    real_data.append(full_info)
            
            # 排序排行清單
            rank_list = sorted(real_data, key=lambda x: x['annual_return'], reverse=True)

            # 3. 個人持股與全資產產業統計
            cursor.execute("""
                SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance 
                FROM user_portfolio p
                JOIN etf_tickers t ON p.stock_code = t.ticker
                WHERE p.user_id = %s
            """, (user_id,))
            
            for item in cursor.fetchall():
                full_info = get_full_etf_data(item['ticker_yfinance'])
                if full_info:
                    my_portfolio_data.append({
                        'name': item['stock_name'], 'code': item['stock_code'], 
                        'price': full_info['price'], 'change': full_info['change'],
                        'annual_return': full_info['annual_return'], 'amp': full_info['amp'],
                        'pos': full_info['pos']
                    })
                    
                    # 統計產業分佈
                    try:
                        t = yf.Ticker(item['ticker_yfinance'])
                        holdings = t.funds_data.top_holdings
                        if holdings is not None and not holdings.empty:
                            for i in range(len(holdings)):
                                stock_en = str(holdings.iloc[i].iloc[0])
                                weight = float(holdings.iloc[i].iloc[1]) * 100
                                s_name = sector_lookup.get(stock_en, "其他")
                                all_sector_dist[s_name] = all_sector_dist.get(s_name, 0) + weight
                    except: continue

        # 整理 Chart.js 資料
        dashboard_sector_analysis = sorted(
            [{"label": k, "value": round(v, 2)} for k, v in all_sector_dist.items()],
            key=lambda x: x['value'], reverse=True
        )

        # 資料校對報告 (Print)
        print("\n--- [資料校對報告] ---")
        for s in my_portfolio_data:
            print(f"標的: {s['code']}, 價格: {s['price']}, 位階: {s['pos']}")
        total_weight = sum(item['value'] for item in dashboard_sector_analysis)
        print(f"總產業權重加總: {total_weight}% (識別率)\n--------------------\n")

    except Exception as e:
        print(f"主首頁讀取錯誤: {e}")
        dashboard_sector_analysis = []
    finally:
        db.close()

    return render_template('index.html', stocks=real_data, rank_list=rank_list, 
                           my_stocks=my_portfolio_data, username=session.get('username'),
                           dashboard_sector_analysis=dashboard_sector_analysis)

if __name__ == '__main__':
    app.run(debug=True)
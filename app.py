from flask import Flask, redirect, url_for, render_template, session
import yfinance as yf
from datetime import datetime
from service.auth import auth_bp
from service.portfolio import portfolio_bp
from service.recommend import recommend_bp, cache 
from service.models import get_db_connection

app = Flask(__name__)
app.secret_key = 'your_key'
cache.init_app(app)

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(portfolio_bp, url_prefix='/portfolio')
app.register_blueprint(recommend_bp, url_prefix='/recommend')

@app.route('/')
def index():
    return redirect(url_for('auth.login'))

# --- 💡 核心工具函數：快取化 ---
@cache.memoize(timeout=3600)
def get_full_etf_data(ticker_yfinance):
    try:
        ticker = yf.Ticker(ticker_yfinance)
        hist_3m = ticker.history(period="3mo")
        if hist_3m.empty or len(hist_3m) < 2: return None

        latest, prev = hist_3m.iloc[-1], hist_3m.iloc[-2]
        current_price, yesterday_close = latest["Close"], prev["Close"]
        
        hist_1y = ticker.history(period="1y")
        annual_return = ((hist_1y["Close"].iloc[-1] - hist_1y["Close"].iloc[0]) / hist_1y["Close"].iloc[0] * 100) if not hist_1y.empty else 0

        past_3m = hist_3m.iloc[:-1]
        max_30, min_30 = past_3m.tail(20)['High'].max(), past_3m.tail(20)['Low'].min()
        max_90, min_90 = past_3m['High'].max(), past_3m['Low'].min()

        return {
            "price": round(current_price, 2),
            "last_close": round(yesterday_close, 2),
            "change": round(((current_price - yesterday_close) / yesterday_close) * 100, 2),
            "annual_return": round(annual_return, 2),
            "amp": round(((latest["High"] - latest["Low"]) / yesterday_close) * 100, 2),
            "pos": {
                "is_30d_high": current_price >= max_30 * 0.99,
                "is_30d_low": current_price <= min_30 * 1.01,
                "is_90d_high": current_price >= max_90 * 0.99,
                "is_90d_low": current_price <= min_90 * 1.01,
            },
            "month_high": round(max_30, 2), "month_low": round(min_30, 2),
            "quarter_high": round(max_90, 2), "quarter_low": round(min_90, 2)
        }
    except: return None

# --- 優化版主頁 ---
@app.route('/index')
def home():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    
    db = get_db_connection()
    user_id = session.get('user_id')
    real_data, my_portfolio_data, all_sector_dist = [], [], {}
    
    try:
        with db.cursor() as cursor:
            # 1. 產業映射
            cursor.execute("SELECT m.name_en, s.sector_name FROM stock_name_map m LEFT JOIN stock_sectors s ON m.sector_id = s.id")
            sector_lookup = {r['name_en']: r['sector_name'] for r in cursor.fetchall()}

            # 2. 市場焦點
            cursor.execute("SELECT name, ticker, ticker_yfinance FROM etf_tickers ORDER BY rand() LIMIT 5")
            for item in cursor.fetchall():
                info = get_full_etf_data(item['ticker_yfinance'])
                if info:
                    info.update({'name': item['name'], 'code': item['ticker']})
                    real_data.append(info)
            
            # 3. 個人持股與產業統計 (減少重複爬蟲)
            cursor.execute("SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance FROM user_portfolio p JOIN etf_tickers t ON p.stock_code = t.ticker WHERE p.user_id = %s", (user_id,))
            portfolio_items = cursor.fetchall()
            
            for item in portfolio_items:
                info = get_full_etf_data(item['ticker_yfinance'])
                if info:
                    my_portfolio_data.append({**info, 'name': item['stock_name'], 'code': item['stock_code']})
                    # 統計產業分佈
                    t = yf.Ticker(item['ticker_yfinance'])
                    holdings = t.funds_data.top_holdings
                    if holdings is not None and not holdings.empty:
                        for i in range(len(holdings)):
                            s_name = sector_lookup.get(str(holdings.iloc[i].iloc[0]), "其他")
                            all_sector_dist[s_name] = all_sector_dist.get(s_name, 0) + (float(holdings.iloc[i].iloc[1]) * 100)

    finally: db.close()

    return render_template('index.html', 
        stocks=real_data, 
        rank_list=sorted(real_data, key=lambda x: x['annual_return'], reverse=True), 
        my_stocks=my_portfolio_data, 
        username=session.get('username'),
        dashboard_sector_analysis=sorted([{"label": k, "value": round(v, 2)} for k, v in all_sector_dist.items()], key=lambda x: x['value'], reverse=True))

if __name__ == '__main__':
    app.run(debug=False) # 💡 Demo 前請務必關閉 debug
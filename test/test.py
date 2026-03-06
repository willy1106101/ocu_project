import yfinance as yf
import pandas as pd
def get_sector_weights(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    
    # 注意：產業比重存放在 funds_data 中
    weights = ticker.funds_data.sector_weightings
    
    if weights:
        # yfinance 回傳的是一個 dictionary，例如 {'technology': 0.45, 'financial': 0.20, ...}
        return weights
    else:
        return None

# 測試
# print(get_sector_weights("0050.TW"))


def get_etf_holdings_fixed(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        holdings = ticker.funds_data.top_holdings
        
        if holdings is not None and not holdings.empty:
            # 檢查欄位數量
            cols = holdings.columns.tolist()
            print(f"修正處理中，欄位為: {cols}")
            
            result = []
            for i in range(len(holdings)):
                row = holdings.iloc[i]
                
                # 根據你目前的欄位 ['Name', 'Holding Percent'] 抓取
                # row.iloc[0] 是 Name
                # row.iloc[1] 是 Holding Percent
                
                name_raw = str(row.iloc[0])
                weight_val = float(row.iloc[1])
                
                result.append({
                    'name': name_raw,
                    'symbol': 'N/A', # 因為 Yahoo 沒給代號，先填 N/A
                    'weight': round(weight_val * 100, 2)
                })
            return result
        else:
            return []
    except Exception as e:
        print(f"發生錯誤: {e}")
        return []
# 測試：0050 
print(get_etf_holdings_fixed("0050.TW"))
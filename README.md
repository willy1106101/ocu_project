# OCU ETF 專案（XAMPP 友善版）

本專案保留可搭配 XAMPP 開發的方式，重點是把「前置作業簡化為固定流程」，並降低常見初始化錯誤。

## 專案結構（已整理）

```text
.
├── app.py                         # 啟動入口（維持 python app.py）
├── ocu_app/                       # Flask 主程式
│   ├── __init__.py                # create_app + 主路由
│   ├── blueprints/                # auth / portfolio / recommend
│   ├── core/                      # config / db model / decorators
│   ├── services/                  # 外部資料服務（yfinance）
│   ├── templates/                 # Jinja2 templates
│   └── static/                    # 靜態資源
├── database/                      # 資料庫檔案分層
│   ├── schema/                    # 建表 SQL
│   ├── seed/                      # 種子資料 SQL
│   └── backup/                    # 備份 SQL
├── scripts/
│   └── init_db.py                 # 一鍵初始化資料庫
├── docs/
│   ├── revamp.md                  # 重構紀錄
│   └── onboarding_setup_test.md   # 新人架設與測試手冊
├── .env.example
└── requirements.txt
```

## 1) 先啟動 XAMPP

至少啟動 `MySQL`。  
`Apache` 是否啟動不影響 Flask 本地開發。

## 2) 安裝 Python 依賴

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

若執行 `Activate.ps1` 被系統阻擋，可先在同一個 PowerShell 視窗執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 3) 建立環境設定檔

```powershell
Copy-Item .\.env.example .\.env
```

若你在 XAMPP 改過 MySQL 設定，請調整 `.env` 的 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD`。

## 4) 以 phpMyAdmin 手動匯入（完整建置必做）

若要以你指定的流程完整建置，請在 phpMyAdmin 依序匯入下列 SQL。

1. 先建立資料庫 `ocu_project`（Collation 建議 `utf8mb4_unicode_ci`）。
2. 匯入 `database/schema/schema.sql`（先補齊必要資料表）。
3. 匯入 `database/backup/ocu_project_2025_1230.sql`。
4. 匯入 `database/seed/etf_types.sql`。
5. 匯入 `database/seed/etf_tickers.sql`。

重點：

1. 這三份檔案是完整資料的核心：  
`ocu_project_2025_1230.sql`、`etf_types.sql`、`etf_tickers.sql`
2. `schema.sql` 是前置建表檔，避免 `etf_types`/`etf_tickers` 表不存在導致匯入失敗。

可在 phpMyAdmin 的 SQL 分頁執行以下檢查：

```sql
SELECT COUNT(*) AS etf_type_count FROM etf_types;
SELECT COUNT(*) AS etf_ticker_count FROM etf_tickers;
SELECT COUNT(*) AS user_count FROM users;
```

### #1451 外鍵錯誤修正說明（已內建）

`database/backup/ocu_project_2025_1230.sql` 已修正為：

1. 先刪除子表 `user_portfolio`，再刪除父表 `users`
2. 避免匯入時因外鍵依賴導致 `#1451 Cannot delete or update a parent row`

若你在 phpMyAdmin 匯入時仍遇到 #1451，可先在 SQL 視窗執行：

```sql
USE ocu_project;
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS user_portfolio;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;
```

再重新匯入：`database/backup/ocu_project_2025_1230.sql`

### #1267 Collation 錯誤修正說明（已內建）

`database/backup/ocu_project_2025_1230.sql` 已統一為 `utf8mb4_unicode_ci`，避免與
`schema.sql` / seed 檔混用時出現：

`Illegal mix of collations (utf8mb4_general_ci) and (utf8mb4_unicode_ci)`

若你是舊資料庫升級（不是全新匯入）且仍遇到 #1267，可在 SQL 視窗執行：

```sql
USE ocu_project;
ALTER TABLE user_portfolio CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE etf_list CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE etf_composition CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 4A) 一鍵腳本（可選）

若你不透過 phpMyAdmin 手動匯入，也可改用：

```powershell
python .\scripts\init_db.py
```

## 5) 啟動專案

```powershell
python .\app.py
```

預設開啟：`http://127.0.0.1:5000`

## 常見問題

1. 出現 MySQL 連線失敗  
先確認 XAMPP 的 MySQL 已啟動，再檢查 `.env` 參數。

2. 出現找不到資料表  
請確認已在 phpMyAdmin 依序匯入：  
`database/schema/schema.sql` → `database/backup/ocu_project_2025_1230.sql` → `database/seed/etf_types.sql` → `database/seed/etf_tickers.sql`。

3. 想調整推薦規則  
可在 `.env` 設定 `RISK_TYPE_MAP_JSON`，例如：  
`{"低風險":[1,4],"中風險":[2,4,10],"高風險":[3,7,8]}`

4. 匯入 `ocu_project_2025_1230.sql` 出現 `#1451`  
請先執行上方「#1451 外鍵錯誤修正說明」中的清理 SQL，再重匯。

## 其他文件

1. 重構細節：`docs/revamp.md`
2. 新人架設與測試：`docs/onboarding_setup_test.md`

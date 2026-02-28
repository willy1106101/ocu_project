# OCU 專案新手上手：架設與測試指南

此文件給第一次接手專案的同事，目標是「可以在本機穩定跑起來，並完成一輪基本驗證」。

## 專案結構快速理解

1. `app.py`：啟動入口。
2. `ocu_app/`：Flask 程式主體（blueprints/core/services/templates/static）。
3. `database/`：SQL 分層（`schema` / `seed` / `backup`）。
4. `scripts/init_db.py`：一鍵初始化資料庫。
5. `docs/`：交接與操作文件。

## 0) 你需要先準備

1. XAMPP（需要啟動 MySQL）。
2. Python 3.10 以上。
3. 具備終端機操作權限。

---

## 1) 啟動本機 MySQL（XAMPP）

1. 開啟 XAMPP Control Panel。
2. 啟動 `MySQL`。
3. 確認埠號（預設 `3306`）。

說明：

- 此專案是 Flask + MySQL。  
- `Apache` 非必要（除非你有其他反向代理需求）。

---

## 2) 安裝專案依賴

在專案根目錄執行：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

若 `Activate.ps1` 被阻擋，先在同一個 PowerShell 視窗執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 3) 建立環境設定檔

```powershell
Copy-Item .\.env.example .\.env
```

常見要調整的欄位：

1. `DB_HOST`
2. `DB_PORT`
3. `DB_USER`
4. `DB_PASSWORD`
5. `DB_NAME`

若你用 XAMPP 預設值，通常可直接使用範本。

---

## 4) 在 phpMyAdmin 匯入資料庫（必要）

請在 phpMyAdmin 依序執行：

1. 建立資料庫 `ocu_project`。
2. 匯入 `database/schema/schema.sql`。
3. 匯入 `database/backup/ocu_project_2025_1230.sql`。
4. 匯入 `database/seed/etf_types.sql`。
5. 匯入 `database/seed/etf_tickers.sql`。

重點：

1. 完整建置必須包含你指定的三份資料檔：  
`ocu_project_2025_1230.sql`、`etf_types.sql`、`etf_tickers.sql`
2. `schema.sql` 是前置建表檔，避免 `etf_types/etf_tickers` 不存在造成匯入失敗。

可在 phpMyAdmin SQL 頁籤確認：

```sql
SELECT COUNT(*) AS etf_type_count FROM etf_types;
SELECT COUNT(*) AS etf_ticker_count FROM etf_tickers;
SELECT COUNT(*) AS user_count FROM users;
```

補充：

`database/backup/ocu_project_2025_1230.sql` 已處理 `users` / `user_portfolio` 外鍵刪除順序，避免常見 `#1451` 匯入錯誤。

## 4A) 一鍵初始化腳本（可選）

若不走 phpMyAdmin 手動匯入，可改用：

```powershell
python .\scripts\init_db.py
```

---

## 5) 啟動專案

```powershell
python .\app.py
```

預設網址：

`http://127.0.0.1:5000`

---

## 6) 最小功能測試（Smoke Test）

請按以下順序走一次：

1. 開啟登入頁面，畫面正常顯示。
2. 註冊新帳號（含 email、id_card）。
3. 登入成功後進入首頁 `/index`。
4. 進入「個人設定」頁，修改風險等級並儲存。
5. 進入「股票管理」新增一筆持股，確認列表顯示。
6. 進入「推薦系統」，確認推薦卡片正常顯示。
7. 在推薦頁做兩檔 ETF 比較，確認可看到分析結果頁。
8. 登出後重新進入受保護頁，應被導回登入頁。

---

## 7) 錯誤情境測試（建議做）

1. 關閉 XAMPP MySQL 後刷新頁面，應收到 DB 連線失敗提示，而不是直接 crash。
2. 刪掉資料庫後重跑 `python .\scripts\init_db.py`，應可重新建置成功。
3. 在比較頁選同一檔 ETF，應收到提示訊息，不應進入錯誤頁。

---

## 8) 常見問題排查

### 問題 A：`ModuleNotFoundError: pymysql`

原因：

- 尚未安裝依賴。

處理：

```powershell
python -m pip install -r .\requirements.txt
```

### 問題 B：資料表不存在（`Table ... doesn't exist`）

原因：

- 沒有在 phpMyAdmin 完成 SQL 匯入，或匯入順序錯誤。

處理：

請重新依序匯入：  
`database/schema/schema.sql` → `database/backup/ocu_project_2025_1230.sql` → `database/seed/etf_types.sql` → `database/seed/etf_tickers.sql`

### 問題 C：MySQL 連線失敗

檢查：

1. XAMPP MySQL 是否已啟動。
2. `.env` 的 DB 帳密、host、port 是否正確。
3. 是否有其他程式占用同埠。

### 問題 D：匯入 `ocu_project_2025_1230.sql` 出現 `#1451`

原因：

- 資料庫內已有 `user_portfolio -> users` 外鍵關係，匯入時刪除父表遭阻擋。

處理：

先在 phpMyAdmin SQL 視窗執行：

```sql
USE ocu_project;
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS user_portfolio;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;
```

再重新匯入：`database/backup/ocu_project_2025_1230.sql`

---

## 9) 建議交接基線

完成以下項目再交給下一位同事：

1. `scripts/init_db.py` 可成功執行。
2. `python .\app.py` 可正常啟動。
3. Smoke test 8 個步驟至少跑過一次。
4. `.env` 不要提交到版本控制。

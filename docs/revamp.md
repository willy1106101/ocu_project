# OCU Project Revamp 與架構整理紀錄

## 本次目標

1. 保留 XAMPP（MySQL）作為主要開發前提。
2. 簡化專案啟動前置流程。
3. 降低初始化與執行時常見錯誤。
4. 將原本散落在根目錄的檔案分層分類，提升可維護性。

---

## 架構整理前後差異

### Before（主要痛點）

1. 根目錄混放 Flask 模組、SQL、文件與資源。
2. 程式與資料庫檔案沒有明確分層。
3. 文件提到的路徑與實際維護習慣不一致。

### After（目前狀態）

1. 程式碼集中於 `ocu_app/`。
2. SQL 分為 `database/schema`, `database/seed`, `database/backup`。
3. 文件集中於 `docs/`。
4. 保留 `python app.py` 啟動，不增加操作複雜度。

---

## 新目錄分層

```text
.
├── app.py
├── ocu_app/
│   ├── __init__.py
│   ├── blueprints/
│   │   ├── auth.py
│   │   ├── portfolio.py
│   │   └── recommend.py
│   ├── core/
│   │   ├── config.py
│   │   ├── models.py
│   │   └── decorators.py
│   ├── services/
│   │   └── market_data.py
│   ├── templates/
│   └── static/
├── database/
│   ├── schema/schema.sql
│   ├── seed/etf_types.sql
│   ├── seed/etf_tickers.sql
│   └── backup/ocu_project_2025_1230.sql
├── scripts/init_db.py
├── docs/
│   ├── revamp.md
│   └── onboarding_setup_test.md
└── legacy/etf_analysis.py
```

---

## 主要重構內容

### A. 程式層重整

1. `app.py` 改為純啟動入口。
2. `create_app` 與首頁主路由移到 `ocu_app/__init__.py`。
3. Blueprint 拆分集中於 `ocu_app/blueprints/`。
4. 共用核心模組集中於 `ocu_app/core/`。
5. 市場資料服務集中於 `ocu_app/services/`。
6. `templates/static` 移入 `ocu_app/`，由 Flask package 直接管理。

### B. DB 檔案重整

1. 建表檔移至 `database/schema/schema.sql`。
2. ETF 種子資料移至 `database/seed/`。
3. 備份 SQL 移至 `database/backup/`。
4. `scripts/init_db.py` 路徑同步更新為新結構。
5. 修正 `ocu_project_2025_1230.sql` 的外鍵刪除順序（先刪 `user_portfolio` 再刪 `users`），降低 phpMyAdmin 匯入 `#1451` 發生率。
6. `etf_types.sql`、`etf_tickers.sql` 補上建表與 `INSERT IGNORE`，支援重複匯入。

### C. 文件重整

1. 重構紀錄移至 `docs/revamp.md`。
2. 新人手冊移至 `docs/onboarding_setup_test.md`。
3. `README.md` 補上新目錄樹與文件入口。

---

## 啟動方式（維持不變）

```bash
python app.py
```

## 初始化方式（路徑已更新）

```bash
python scripts/init_db.py
```

---

## 注意事項

1. 若尚未安裝依賴，`init_db.py` 會缺少 `pymysql`。
2. `.env` 仍由 `.env.example` 複製，不納入版本控制。
3. 本次重整以「可用、可讀、可交接」為優先，未增加新執行步驟。

CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT,
    id_card VARCHAR(20) NOT NULL,
    username VARCHAR(50) NOT NULL,
    phone VARCHAR(20) NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    risk_level VARCHAR(10) DEFAULT '中風險',
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_id_card (id_card),
    UNIQUE KEY uk_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS etf_types (
    id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_etf_types_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS etf_tickers (
    id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    ticker_yfinance VARCHAR(20) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    types INT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_etf_tickers_ticker (ticker),
    UNIQUE KEY uk_etf_tickers_yf (ticker_yfinance),
    KEY idx_etf_tickers_types (types),
    CONSTRAINT fk_etf_tickers_types FOREIGN KEY (types) REFERENCES etf_types (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_portfolio (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    stock_name VARCHAR(50) NULL,
    stock_code VARCHAR(20) NULL,
    buy_price FLOAT NULL,
    dividend FLOAT NULL,
    current_price FLOAT NULL,
    buy_date DATE NULL,
    PRIMARY KEY (id),
    KEY idx_user_portfolio_user_id (user_id),
    KEY idx_user_portfolio_stock_code (stock_code),
    CONSTRAINT fk_user_portfolio_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS etf_composition (
    id INT NOT NULL AUTO_INCREMENT,
    etf_code VARCHAR(10) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(50) NOT NULL,
    weight FLOAT NOT NULL,
    PRIMARY KEY (id),
    KEY idx_etf_composition_etf_code (etf_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

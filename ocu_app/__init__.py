from flask import Flask, current_app, flash, redirect, render_template, session, url_for

from .blueprints.auth import auth_bp
from .blueprints.portfolio import portfolio_bp
from .blueprints.recommend import recommend_bp
from .core.config import AppConfig
from .core.decorators import login_required
from .core.models import DatabaseConnectionError, get_db_connection
from .services.market_data import get_etf_snapshot


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(AppConfig)
    app.secret_key = app.config["SECRET_KEY"]

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(portfolio_bp, url_prefix="/portfolio")
    app.register_blueprint(recommend_bp, url_prefix="/recommend")

    _register_routes(app)
    return app


def _register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/index")
    @login_required
    def home():
        user_id = session["user_id"]
        focus_limit = max(1, int(current_app.config["FOCUS_ETF_LIMIT"]))
        one_year_period = current_app.config["ONE_YEAR_PERIOD"]
        recent_period = current_app.config["RECENT_PERIOD"]

        real_data = []
        my_portfolio_data = []
        rank_list = []
        db = None

        try:
            db = get_db_connection()
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT name, ticker, ticker_yfinance
                    FROM etf_tickers
                    ORDER BY RAND()
                    LIMIT %s
                    """,
                    (focus_limit,),
                )
                tickers = cursor.fetchall()

                for item in tickers:
                    snapshot = get_etf_snapshot(
                        item["ticker_yfinance"],
                        one_year_period=one_year_period,
                        recent_period=recent_period,
                    )
                    real_data.append(
                        {
                            "name": item["name"],
                            "code": item["ticker"],
                            "price": snapshot["current_price"],
                            "change": snapshot["change_percent"],
                            "open": snapshot["open_price"],
                            "last_close": snapshot["yesterday_close"],
                            "annual_return": snapshot["annual_return"],
                        }
                    )

                rank_list = sorted(
                    real_data, key=lambda row: row["annual_return"], reverse=True
                )

                cursor.execute(
                    """
                    SELECT DISTINCT p.stock_name, p.stock_code, t.ticker_yfinance
                    FROM user_portfolio p
                    JOIN etf_tickers t ON p.stock_code = t.ticker
                    WHERE p.user_id = %s
                    """,
                    (user_id,),
                )
                my_tickers = cursor.fetchall()

                for item in my_tickers:
                    snapshot = get_etf_snapshot(
                        item["ticker_yfinance"],
                        one_year_period=one_year_period,
                        recent_period=recent_period,
                    )
                    my_portfolio_data.append(
                        {
                            "name": item["stock_name"],
                            "code": item["stock_code"],
                            "open": snapshot["open_price"],
                            "price": snapshot["current_price"],
                            "change": snapshot["change_percent"],
                            "last_close": snapshot["yesterday_close"],
                            "amp": snapshot["amplitude"],
                            "annual_return": snapshot["annual_return"],
                        }
                    )
        except DatabaseConnectionError as exc:
            current_app.logger.exception("Database connection failed: %s", exc)
            flash("資料庫連線失敗，請確認 XAMPP MySQL 已啟動與 .env 設定。", "danger")
        except Exception as exc:
            current_app.logger.exception("Home data loading failed: %s", exc)
            flash("資料讀取失敗，請稍後再試。", "danger")
        finally:
            if db:
                db.close()

        return render_template(
            "index.html",
            stocks=real_data,
            rank_list=rank_list,
            my_stocks=my_portfolio_data,
            username=session.get("username"),
        )

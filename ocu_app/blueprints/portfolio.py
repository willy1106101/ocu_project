from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from ..core.decorators import login_required
from ..core.models import DatabaseConnectionError, get_db_connection

portfolio_bp = Blueprint("portfolio", __name__)


def _to_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


@portfolio_bp.route("/list")
@login_required
def list_stocks():
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM user_portfolio WHERE user_id = %s ORDER BY buy_date DESC, id DESC",
                (session["user_id"],),
            )
            my_stocks = cursor.fetchall()
        return render_template("portfolio_list.html", stocks=my_stocks)
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
        return redirect(url_for("home"))
    except Exception as exc:
        current_app.logger.exception("Load portfolio failed: %s", exc)
        flash("讀取持股失敗，請稍後再試。", "danger")
        return redirect(url_for("home"))
    finally:
        if db:
            db.close()


@portfolio_bp.route("/add", methods=["POST"])
@login_required
def add_stock():
    stock_name = (request.form.get("stock_name") or "").strip()
    stock_code = (request.form.get("stock_code") or "").strip()
    buy_date = request.form.get("buy_date")

    if not stock_name or not stock_code or not buy_date:
        flash("請完整填寫股票名稱、代碼與成交日期。", "danger")
        return redirect(url_for("portfolio.list_stocks"))

    data = (
        session["user_id"],
        stock_name,
        stock_code,
        _to_float(request.form.get("buy_price")),
        _to_float(request.form.get("dividend")),
        _to_float(request.form.get("current_price")),
        buy_date,
    )

    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_portfolio
                (user_id, stock_name, stock_code, buy_price, dividend, current_price, buy_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                data,
            )
        db.commit()
        flash("股票新增成功。", "success")
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
    except Exception as exc:
        if db:
            db.rollback()
        current_app.logger.exception("Add stock failed: %s", exc)
        flash("新增失敗，請確認資料格式。", "danger")
    finally:
        if db:
            db.close()

    return redirect(url_for("portfolio.list_stocks"))


@portfolio_bp.route("/delete/<int:id>")
@login_required
def delete_stock(id):
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "DELETE FROM user_portfolio WHERE id = %s AND user_id = %s",
                (id, session["user_id"]),
            )
        db.commit()
        flash("資料已刪除。", "info")
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
    except Exception as exc:
        if db:
            db.rollback()
        current_app.logger.exception("Delete stock failed: %s", exc)
        flash("刪除失敗，請稍後再試。", "danger")
    finally:
        if db:
            db.close()

    return redirect(url_for("portfolio.list_stocks"))

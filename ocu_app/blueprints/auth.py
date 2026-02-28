from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from ..core.decorators import login_required
from ..core.models import DatabaseConnectionError, get_db_connection

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        id_card = (request.form.get("id_card") or "").strip()
        username = (request.form.get("username") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not id_card or not username or not email or not password:
            flash("請完整填寫必填欄位。", "danger")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)
        db = None

        try:
            db = get_db_connection()
            with db.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE email = %s OR id_card = %s",
                    (email, id_card),
                )
                if cursor.fetchone():
                    flash("此 Email 或身分證字號已被註冊。", "danger")
                    return render_template("register.html")

                cursor.execute(
                    """
                    INSERT INTO users (id_card, username, phone, email, password)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (id_card, username, phone or None, email, hashed_password),
                )
            db.commit()
            flash("註冊成功，請登入。", "success")
            return redirect(url_for("auth.login"))
        except DatabaseConnectionError as exc:
            current_app.logger.exception("Database connection failed: %s", exc)
            flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
        except Exception as exc:
            if db:
                db.rollback()
            current_app.logger.exception("Register failed: %s", exc)
            flash("註冊失敗，請稍後再試。", "danger")
        finally:
            if db:
                db.close()

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("請輸入帳號與密碼。", "danger")
            return render_template("login.html")

        db = None
        try:
            db = get_db_connection()
            with db.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["risk_level"] = user["risk_level"] or "中風險"
                flash(f'歡迎回來，{user["username"]}。', "success")
                return redirect(url_for("home"))

            flash("帳號或密碼錯誤，請重新輸入。", "danger")
        except DatabaseConnectionError as exc:
            current_app.logger.exception("Database connection failed: %s", exc)
            flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
        finally:
            if db:
                db.close()

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("您已成功登出。", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_card, username, phone, email, risk_level
                FROM users
                WHERE id = %s
                """,
                (session["user_id"],),
            )
            user_info = cursor.fetchone()
        return render_template("profile.html", user=user_info)
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
        return redirect(url_for("home"))
    except Exception as exc:
        current_app.logger.exception("Profile load failed: %s", exc)
        flash("讀取個人資料失敗，請稍後再試。", "danger")
        return redirect(url_for("home"))
    finally:
        if db:
            db.close()


@auth_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    new_username = (request.form.get("username") or "").strip()
    new_phone = (request.form.get("phone") or "").strip()
    new_email = (request.form.get("email") or "").strip()
    new_risk = (request.form.get("risk_level") or "中風險").strip()

    if not new_username or not new_email:
        flash("姓名與電子信箱不可為空。", "danger")
        return redirect(url_for("auth.profile"))

    db = None
    try:
        db = get_db_connection()
        with db.cursor() as cursor:
            cursor.execute(
                """
                UPDATE users
                SET username = %s, phone = %s, email = %s, risk_level = %s
                WHERE id = %s
                """,
                (new_username, new_phone or None, new_email, new_risk, session["user_id"]),
            )
        db.commit()
        session["username"] = new_username
        session["risk_level"] = new_risk
        flash("個資修改成功。", "success")
    except DatabaseConnectionError as exc:
        current_app.logger.exception("Database connection failed: %s", exc)
        flash("資料庫連線失敗，請確認 XAMPP MySQL 與 .env 設定。", "danger")
    except Exception as exc:
        if db:
            db.rollback()
        current_app.logger.exception("Profile update failed: %s", exc)
        flash("修改失敗，請確認資料是否重複。", "danger")
    finally:
        if db:
            db.close()

    return redirect(url_for("auth.profile"))

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import get_db_connection
import pymysql

# 建立藍圖
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 取得表單資料
        id_card = request.form.get('id_card')
        username = request.form.get('username')
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')

        # 密碼加密
        hashed_password = generate_password_hash(password)

        db = get_db_connection()
        try:
            with db.cursor() as cursor:
                # 檢查 Email 或 身分證 是否已存在
                check_sql = "SELECT id FROM users WHERE email = %s OR id_card = %s"
                cursor.execute(check_sql, (email, id_card))
                if cursor.fetchone():
                    flash('此 Email 或身分證字號已被註冊！', 'danger')
                    return render_template('register.html')

                # 插入新會員
                sql = """INSERT INTO users (id_card, username, phone, email, password) 
                         VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(sql, (id_card, username, phone, email, hashed_password))
            db.commit()
            flash('註冊成功！請登入', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.rollback()
            flash(f'註冊失敗，錯誤原因：{e}', 'danger')
        finally:
            db.close()

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        db = get_db_connection()
        try:
            with db.cursor() as cursor:
                sql = "SELECT * FROM users WHERE email = %s"
                cursor.execute(sql, (email,))
                user = cursor.fetchone()

                # 驗證使用者存在且密碼正確
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['risk_level'] = user['risk_level']
                    flash(f'歡迎回來，{user["username"]}！', 'success')
                    return redirect(url_for('home')) # 假設首頁在主程式 app.py
                else:
                    flash('帳號或密碼錯誤，請重新輸入', 'danger')
        finally:
            db.close()

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('您已成功登出', 'info')
    return redirect(url_for('auth.login'))

# 個資管理
@auth_bp.route('/profile', methods=['GET'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            # 根據 Session 中的 ID 抓取最新資料
            sql = "SELECT id_card, username, phone, email, risk_level FROM users WHERE id = %s"
            cursor.execute(sql, (session['user_id'],))
            user_info = cursor.fetchone()
        return render_template('profile.html', user=user_info)
    finally:
        db.close()

@auth_bp.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    # 接收表單修改後的資料
    new_username = request.form.get('username')
    new_phone = request.form.get('phone')
    new_email = request.form.get('email')
    new_risk = request.form.get('risk_level') # 讓使用者也可以在這裡改風險等級

    db = get_db_connection()
    try:
        with db.cursor() as cursor:
            sql = """UPDATE users 
                     SET username = %s, phone = %s, email = %s, risk_level = %s 
                     WHERE id = %s"""
            cursor.execute(sql, (new_username, new_phone, new_email, new_risk, session['user_id']))
        db.commit()
        
        # 更新 Session 中的資料，確保網頁顯示同步
        session['username'] = new_username
        session['risk_level'] = new_risk
        
        flash('個資修改成功！', 'success')
    except Exception as e:
        db.rollback()
        flash(f'修改失敗：{e}', 'danger')
    finally:
        db.close()
    
    return redirect(url_for('auth.profile'))

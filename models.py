import pymysql

def get_db_connection():
    # 請根據你的 MySQL 設定修改以下參數
    connection = pymysql.connect(
        host='localhost',       # 主機地址
        user='root',            # 帳號 (通常是 root)
        password='0110936',      # MySQL 密碼
        database='ocu_project',  # 資料庫名稱
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor  # 關鍵：這能讓結果像字典一樣讀取
    )
    return connection
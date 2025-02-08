import sqlite3
import os

# データベースのパス
db_path = os.path.join(os.path.dirname(__file__), "reservations.db")

def initialize_database():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 既存の reservations テーブルを削除
    cur.execute("DROP TABLE IF EXISTS reservations")

    # `reservations` テーブルを作成（正しいカラム構成）
    cur.execute("""
        CREATE TABLE reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            name TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            area TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL
        )
    """)

    # サンプルデータを追加
    cur.execute("""
        INSERT INTO reservations (company, name, employee_id, area, date, start_time, end_time)
        VALUES
        ('A社', '田中一郎', '12345', 'シタシミ', '2025-02-08', '10:00', '12:00'),
        ('B社', '山田花子', '67890', 'キヅキ', '2025-02-09', '14:30', '16:00')
    """)

    conn.commit()
    conn.close()
    print(f"データベース ({db_path}) を作成し、サンプルデータを追加しました！")

if __name__ == "__main__":
    initialize_database()

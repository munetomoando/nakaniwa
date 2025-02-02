from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import and_  
from datetime import datetime
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key"  # `flash` を使うための秘密鍵

# SQLiteデータベースの設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# エリアの表示順を定義
area_order = {
    "シタシミ": 1,
    "キヅキ": 2,
    "ニギワイ": 3,
    "オチツキ": 4,
    "全体貸切": 5
}
# 予約データのテーブル（モデル）
class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(50), nullable=False)  # 企業名
    name = db.Column(db.String(100), nullable=False)  # 氏名
    employee_id = db.Column(db.String(20), nullable=False)  # 社員番号
    area = db.Column(db.String(100), nullable=False)  # 予約エリア（複数選択可能）
    date = db.Column(db.Date, nullable=False)  # ✅ String → Date に変更
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ポイント管理モデル
class CompanyPoints(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(50), unique=True, nullable=False)  # 企業名
    points = db.Column(db.Integer, default=1000)  # 初期ポイント

@app.route('/add_points', methods=['POST'])
def add_points():
    company = request.form.get('company')
    points_to_add = int(request.form.get('points'))

    company_record = CompanyPoints.query.filter_by(company=company).first()
    if company_record:
        company_record.points += points_to_add
    else:
        company_record = CompanyPoints(company=company, points=points_to_add)
        db.session.add(company_record)
    
    db.session.commit()
    return redirect(url_for('reservations_list'))

@app.route('/get_all_company_points')
def get_all_company_points():
    companies = CompanyPoints.query.all()
    points_data = {company.company: company.points for company in companies}
    return jsonify(points_data)


# **日付ごとの予約データを取得**
@app.route('/reservations_by_date')
def reservations_by_date():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if start_date and end_date:
        reservations = Reservation.query.filter(
            Reservation.date >= start_date,
            Reservation.date <= end_date
        ).order_by(Reservation.date, Reservation.start_time).all()
    else:
        return jsonify([])

    reservations_list = [{
        "company": r.company,
        "name": r.name,
        "employee_id": r.employee_id,
        "area": r.area,
        "date": r.date.strftime("%Y-%m-%d"),
        "start_time": r.start_time,
        "end_time": r.end_time
    } for r in reservations]

    return jsonify(reservations_list)



# **予約削除機能**
@app.route('/delete_reservation/<int:reservation_id>', methods=['POST'])
def delete_reservation(reservation_id):
    reservation = Reservation.query.get(reservation_id)
    if reservation:
        db.session.delete(reservation)
        db.session.commit()
        return redirect(url_for('reservations_list', date=reservation.date))
    return "エラー: 予約が見つかりませんでした。"

# **特定の日の予約データを表形式で表示（削除ボタン付き）**
@app.route('/reservations_list', methods=['GET'])
def reservations_list():
    date = request.args.get('date')
    range_type = request.args.get('range')

    today = datetime.today().strftime('%Y-%m-%d')

    if range_type == "7days":
        end_date = (datetime.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        reservations = Reservation.query.filter(
            and_(Reservation.date >= today, Reservation.date <= end_date)
        ).order_by(Reservation.date, Reservation.start_time).all()
    elif range_type == "month":
        end_date = (datetime.today().replace(day=1) + timedelta(days=31)).strftime('%Y-%m-%d')
        reservations = Reservation.query.filter(
            and_(Reservation.date >= today, Reservation.date <= end_date)
        ).order_by(Reservation.date, Reservation.start_time).all()
    elif date:
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date()  # ✅ ここで型変換をチェック
        except ValueError:
            date = None
        reservations = Reservation.query.filter_by(date=date).order_by(Reservation.start_time).all()
    else:
        reservations = []

    return render_template('reservations_list.html', reservations=reservations, selected_date=date, range_type=range_type)

# 企業ごとのポイントを管理するテーブル
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 企業名
    points = db.Column(db.Integer, nullable=False, default=1000)  # 所有ポイント（初期値1000）


# **データベースの初期化**
def init_db():
    with app.app_context():
        db.create_all()
        print("データベース (reservations.db) が作成されました！")

        # 企業情報を登録
        if not Company.query.first():  # すでにデータがある場合は追加しない
            companies = ["A社", "B社", "C社", "D社", "E社", "F社"]
            for name in companies:
                company = Company(name=name, points=1000)
                db.session.add(company)
            db.session.commit()
            print("企業情報をデータベースに追加しました！")
# **毎月1日に企業のポイントをリセット**
def reset_points():
    with app.app_context():
        companies = Company.query.all()
        for company in companies:
            company.points = 1000
        db.session.commit()
        print("企業のポイントをリセットしました！")

# **予約時のポイント計算**
def calculate_points(date, start_time_str, end_time_str, num_areas):
    # start_time と end_time は文字列として渡されているので変換
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.strptime(end_time_str, "%H:%M").time()

    # ✅ date が datetime.date 型ならそのまま weekday() を使用
    if isinstance(date, str):
        weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
    else:
        weekday = date.weekday()

    # 30分単位での予約時間の計算
    duration = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)).total_seconds() / 1800

    # ピーク時間帯の判定
    is_peak_time = (weekday == 0 and start_time < time(12, 0)) or (weekday == 4 and end_time > time(13, 0))

    cost_per_30min = 20 if is_peak_time else 10
    total_cost = int(duration) * cost_per_30min * num_areas
    return max(total_cost, 0)

@app.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if request.method == 'POST':
        company_name = request.form['company']
        name = request.form['name']
        employee_id = request.form['employee_id']
        areas = request.form.getlist('area')  # 複数選択のエリア
        date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
        start_time_str = request.form['start_time']
        end_time_str = request.form['end_time']
        start_time = datetime.strptime(request.form['start_time'], "%H:%M").time()
        end_time = datetime.strptime(request.form['end_time'], "%H:%M").time()


        # 選択したエリアをカンマ区切りで保存
        area = ", ".join(areas)

        # **エリア予約の重複チェック**
        all_areas = {"キヅキ", "オチツキ", "シタシミ", "ニギワイ"}  # ✅ エリアのセット

        is_full_reservation = "全体貸切" in areas  # 貸切が選ばれているか
        reserved_areas = set(areas)  # 予約しようとしているエリア（セット）

        # **データベース内の既存予約を取得**
        existing_reservations = Reservation.query.filter(
            and_(
                Reservation.date == date,
                Reservation.start_time < end_time_str,
                Reservation.end_time > start_time_str
            )
        ).all()

        # **貸切 vs 通常エリアの競合チェック**
        for res in existing_reservations:
            existing_reserved_areas = set(res.area.split(", "))  # 既存予約のエリア（セット）

            if is_full_reservation:
                if existing_reserved_areas & all_areas:  # 交差があるか
                    return render_template("error.html", message=f"エラー: {date} の {start_time_str} 〜 {end_time_str} はすでに予約されているため、貸切予約できません。")
            else:
                if "全体貸切" in existing_reserved_areas:
                    return render_template("error.html", message=f"エラー: {date} の {start_time_str} 〜 {end_time_str} は貸切予約済みのため、個別エリアの予約はできません。")

        # **企業のポイントを取得**
        company = Company.query.filter_by(name=company_name).first()
        if not company:
            return render_template("error.html", message=f"エラー: 企業情報が見つかりません（{company_name}）")

        # **予約したエリア数をカウント**
        num_areas = len(areas)
        if "全体貸切" in areas:
            num_areas = 4  # 貸切は4エリア分

        # **必要ポイントを計算**
        required_points = calculate_points(date, start_time_str, end_time_str, num_areas)

        # **ポイントが足りない場合はエラー**
        if company.points < required_points:
            return render_template("error.html", message=f"エラー: ポイントが不足しています（必要: {required_points}pt, 保有: {company.points}pt）")

        # **予約データをデータベースに保存**
        new_reservation = Reservation(
            company=company_name,
            name=name,
            employee_id=employee_id,
            area=area,
            date=date,
            start_time=start_time_str,
            end_time=end_time_str
        )
        db.session.add(new_reservation)

        # **ポイントを減らす**
        company.points -= required_points
        db.session.commit()

        return f"予約完了: {date} の {start_time_str} から {end_time_str} まで {area} を予約しました！（企業: {company_name}, 消費ポイント: {required_points}pt, 残り: {company.points}pt）"

    return render_template('reservation.html')



@app.route('/calculate_points', methods=['GET'])
def get_required_points():
    date = request.args.get('date')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    num_areas = request.args.get('num_areas', "1")  # デフォルト1

    if not date or not start_time or not end_time:
        return jsonify({"points": 0})

    try:
        num_areas = int(num_areas)  # 確実に整数に変換
    except ValueError:
        return jsonify({"error": "エリア数が無効です"}), 400

    required_points = calculate_points(date, start_time, end_time, num_areas)
    return jsonify({"points": required_points})



@app.route('/get_company_points', methods=['GET'])
def get_company_points():
    company_name = request.args.get('company')

    if not company_name:
        return jsonify({"error": "企業名が指定されていません"}), 400

    company = Company.query.filter_by(name=company_name).first()

    if company:
        return jsonify({"points": company.points})
    else:
        return jsonify({"error": "企業が見つかりません"}), 404
        

@app.route('/dashboard/<company>')
def dashboard(company):
    reservations = Reservation.query.filter_by(company=company).all()
    company_points = get_company_points(company)  # 企業ポイントを取得する関数

    # テンプレートファイル名を動的に選択
    template_name = f'dashboard-{company}.html'
    return render_template(template_name, company=company, reservations=reservations, points=company_points)

@app.route('/cancel_reservation/<int:reservation_id>', methods=['POST'])
def cancel_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    db.session.delete(reservation)
    db.session.commit()
    return redirect(url_for('dashboard', company=reservation.company))

if __name__ == '__main__':
    init_db()  # アプリ起動時にデータベースを作成
    app.run(debug=True)

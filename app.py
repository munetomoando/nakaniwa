from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import and_ 
from datetime import datetime, time, timedelta

import json

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
    return Response(json.dumps({"message": "ポイントが加算されました", "success": True}, ensure_ascii=False),
                    mimetype='application/json')

@app.route('/get_all_company_points')
def get_all_company_points():
    # データベースから最新のポイントを取得
    points_data = {}
    companies = ['A社', 'B社', 'C社', 'D社', 'E社', 'F社']
    for company in companies:
        result = db.session.query(CompanyPoints).filter_by(company=company).first()
        if result and result.points is not None:
            points_data[company] = result.points
        else:
            points_data[company] = 0
    return jsonify(points_data)


# **日付ごとの予約データを取得**
@app.route('/reservations_by_date')
def reservations_by_date():
    date_str = request.args.get('date')  # 単一の日付 (例: '2025-02-03')
    start_date_str = request.args.get('start')  # 範囲の開始日 (例: '2025-02-01')
    end_date_str = request.args.get('end')  # 範囲の終了日 (例: '2025-02-07')

    # 単一の日付が指定された場合
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()  # 日付をオブジェクトに変換
        except ValueError:
            return jsonify([])  # 日付の形式が不正な場合、空リストを返す

        # データベースからその日付の予約を取得
        reservations = Reservation.query.filter_by(date=date_obj).order_by(Reservation.start_time).all()

    # 日付範囲が指定された場合
    elif start_date_str and end_date_str:
        try:
            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify([])

        # データベースから範囲内の予約を取得
        reservations = Reservation.query.filter(
            Reservation.date >= start_date_obj,
            Reservation.date <= end_date_obj
        ).order_by(Reservation.date, Reservation.start_time).all()

    else:
        return jsonify([])  # パラメータが指定されていない場合は空リストを返す

    # 取得した予約データをJSON形式で返す
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
    reservations = []

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
    elif range_type == 'next_month':
        today = datetime.now().date()
    
        # 翌月の1日と末日を計算
        first_day_next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        last_day_next_month = (first_day_next_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
        # クエリ用の日付フォーマットに変換
        start_date = first_day_next_month.strftime('%Y-%m-%d')
        end_date = last_day_next_month.strftime('%Y-%m-%d')

        # 翌月の予約データを取得
        reservations = Reservation.query.filter(
            and_(Reservation.date >= start_date, Reservation.date <= end_date)
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
        try:
            # 入力データの取得
            company_name = request.form['company']
            name = request.form['name']
            employee_id = request.form['employee_id']
            areas = request.form.getlist('area')  # 複数選択のエリア
            date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
            start_time_str = request.form['start_time']
            end_time_str = request.form['end_time']
            
            # 開始時間と終了時間をdatetimeオブジェクトに変換
            start_datetime = datetime.strptime(f"{date} {start_time_str}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{date} {end_time_str}", "%Y-%m-%d %H:%M")

            # 時間の逆転チェック
            if start_datetime >= end_datetime:
                return jsonify({"success": False, "message": "終了時間は開始時間より後に設定してください。"}), 400

            area = ", ".join(areas)  # 選択したエリアをカンマ区切りで保存

            # **エリア予約の重複チェック**
            all_areas = {"キヅキ", "オチツキ", "シタシミ", "ニギワイ"}
            new_reservation_areas = set(areas)

            start_time_obj = datetime.strptime(start_time_str, "%H:%M").time()
            end_time_obj = datetime.strptime(end_time_str, "%H:%M").time()
            # 既存の予約を取得（同じ日付で時間が重なるもの）
            existing_reservations = Reservation.query.filter(
                and_(
                    Reservation.date == date,
                    Reservation.start_time < end_time_obj,
                    Reservation.end_time > start_time_obj
                )
            ).all()

            for res in existing_reservations:
                existing_reserved_areas = set(area.strip() for area in res.area.split(", "))

                # 新しい予約が全体貸切の場合
                if "全体貸切" in areas:
                    for res in existing_reservations:
                        existing_reserved_areas = set(area.strip() for area in res.area.split(", "))

                        # 既存の予約が1つでもあればエラー
                        if existing_reserved_areas & all_areas or "全体貸切" in existing_reserved_areas:
                            return jsonify({"message": f"エラー: {date} の {start_time_str} 〜 {end_time_str} はすでに予約されています。"}), 400

                # 既存予約に全体貸切がある場合
                for res in existing_reservations:
                    existing_reserved_areas = set(area.strip() for area in res.area.split(", "))

                    if "全体貸切" in existing_reserved_areas:
                        return jsonify({"message": f"エラー: {date} の {start_time_str} 〜 {end_time_str} は貸切予約済みのため、予約できません。"}), 400

                    # 個別エリアの重複チェック
                    if existing_reserved_areas & new_reservation_areas:
                        return jsonify({"message": f"エラー: {date} の {start_time_str} 〜 {end_time_str} にすでに予約されているエリアがあります。"}), 400

            # 企業のポイントをCompanyPointsテーブルから取得
            company_record = CompanyPoints.query.filter_by(company=company_name).first()
            if not company_record:
                return jsonify({"message": f"エラー: 企業情報が見つかりません（{company_name}）"}), 400

            # **必要ポイントの計算**
            num_areas = 4 if "全体貸切" in areas else len(areas)
            required_points = calculate_points(date, start_time_str, end_time_str, num_areas)

            # ポイントが足りない場合はエラー
            if company_record.points < required_points:
                return jsonify({
                    "message": f"エラー: ポイントが不足しています（必要: {required_points}pt, 保有: {company_record.points}pt）"
                }), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": f"サーバーエラーが発生しました: {str(e)}"}), 500
        try:    # **予約データの保存**
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

            # **ポイントの減算処理**
            if company_record.points < required_points:
                return jsonify({"success": False, "message": "ポイントが不足しています。予約できません。"}), 400

            # **ポイントを減算**
            company_record.points -= required_points
            db.session.commit()

            # **予約完了レスポンス**
            return jsonify(
                success=True,
                message=f"予約完了: {date} の {start_time_str} から {end_time_str} まで {area} を予約しました！",
                remaining_points=company_record.points
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"message": f"サーバーエラーが発生しました: {str(e)}"}), 500

    return render_template('reservation.html')


@app.route('/calculate_points', methods=['GET'])
def calculate_reservation_points():
    date = request.args.get('date')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    num_areas = request.args.get('num_areas')

    # デバッグログ
    print(f"Received: date={date}, start_time={start_time}, end_time={end_time}, num_areas={num_areas}")

    # 入力値のバリデーション
    if not date or not start_time or not end_time or not num_areas:
        return jsonify({'error': 'Invalid input'}), 400

    try:
        num_areas = int(num_areas)
    except ValueError:
        print("Invalid num_areas")
        return jsonify({'error': 'Invalid num_areas'}), 400

    # 時刻の処理
    try:
        num_areas = int(num_areas)
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        duration_minutes = (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)

        if duration_minutes <= 0:
            return jsonify({'error': 'Invalid time range'}), 400

        time_slots = duration_minutes / 30
        base_points_per_area = 10
        total_points = int(base_points_per_area * num_areas * time_slots)

        print(f"Calculated points: {total_points}")
        return jsonify({'points': total_points})

    except Exception as e:
        print(f"Error during calculation: {e}")
        return jsonify({'error': 'Calculation error'}), 500



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

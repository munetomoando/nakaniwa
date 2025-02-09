from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import and_
from datetime import datetime, time, timedelta
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"  # flash用の秘密鍵

# SQLiteデータベースの設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# エリアの表示順（必要に応じて利用）
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
    company = db.Column(db.String(50), nullable=False)    # 企業名
    name = db.Column(db.String(100), nullable=False)        # 氏名
    employee_id = db.Column(db.String(20), nullable=False)    # 社員番号
    area = db.Column(db.String(100), nullable=False)          # 予約エリア（複数選択可）
    date = db.Column(db.Date, nullable=False)                 # 日付型
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    # ケータリング予約情報
    catering_course = db.Column(db.String(10), nullable=True)   # "1000" または "2000"、利用しない場合は None
    catering_people = db.Column(db.Integer, nullable=True)      # 参加人数（2～20）
    # ビール・ワイン予約情報
    beer_count = db.Column(db.Integer, nullable=True)
    wine_sparkling = db.Column(db.Integer, nullable=True)
    wine_white = db.Column(db.Integer, nullable=True)
    wine_red = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company": self.company,
            "name": self.name,
            "employee_id": self.employee_id,
            "area": self.area,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "catering_course": self.catering_course,
            "catering_people": self.catering_people,
            "beer_count": self.beer_count,
            "wine_sparkling": self.wine_sparkling,
            "wine_white": self.wine_white,
            "wine_red": self.wine_red,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None
        }

# 企業ポイント管理モデル
class CompanyPoints(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(50), unique=True, nullable=False)
    points = db.Column(db.Integer, default=1000)

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
    points_data = {}
    companies = ['A社', 'B社', 'C社', 'D社', 'E社', 'F社']
    for company in companies:
        result = CompanyPoints.query.filter_by(company=company).first()
        points_data[company] = result.points if result and result.points is not None else 0
    return jsonify(points_data)

def get_reservations_by_date(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return []
    reservations = Reservation.query.filter_by(date=date_obj).all()
    return [res.to_dict() for res in reservations]

@app.route("/reservations_by_date", methods=["GET"])
def get_daily_reservations():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify([])
    reservations = get_reservations_by_date(date_str)
    return Response(json.dumps(reservations, ensure_ascii=False), mimetype='application/json')

@app.route('/delete_reservation/<int:reservation_id>', methods=['POST'])
def delete_reservation(reservation_id):
    reservation = Reservation.query.get(reservation_id)
    if reservation:
        db.session.delete(reservation)
        db.session.commit()
        return redirect(url_for('reservations_list', date=reservation.date.strftime("%Y-%m-%d")))
    return "エラー: 予約が見つかりませんでした。"

@app.route('/reservations_list', methods=['GET'])
def reservations_list():
    date_param = request.args.get('date')
    range_type = request.args.get('range')
    reservations = []
    selected_date = None
    today = datetime.today().date()
    if range_type == "7days":
        end_date = today + timedelta(days=7)
        reservations = Reservation.query.filter(
            and_(Reservation.date >= today, Reservation.date <= end_date)
        ).order_by(Reservation.date, Reservation.start_time).all()
    elif range_type == "month":
        end_date = (today.replace(day=1) + timedelta(days=31))
        reservations = Reservation.query.filter(
            and_(Reservation.date >= today, Reservation.date < end_date)
        ).order_by(Reservation.date, Reservation.start_time).all()
    elif range_type == 'next_month':
        first_day_next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        last_day_next_month = (first_day_next_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        reservations = Reservation.query.filter(
            and_(Reservation.date >= first_day_next_month, Reservation.date <= last_day_next_month)
        ).order_by(Reservation.date, Reservation.start_time).all()
    elif date_param:
        try:
            selected_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            selected_date = None
        if selected_date:
            reservations = Reservation.query.filter_by(date=selected_date).order_by(Reservation.start_time).all()

    # 企業ポイント情報を取得してテンプレートに渡す
    companies = ['A社', 'B社', 'C社', 'D社', 'E社', 'F社']
    company_points = {company: fetch_company_points(company) for company in companies}

    return render_template(
        'reservations_list.html',
        reservations=reservations,
        selected_date=selected_date,
        range_type=range_type,
        company_points=company_points
    )

def fetch_company_points(company_name):
    company_record = CompanyPoints.query.filter_by(company=company_name).first()
    return company_record.points if company_record else 0

def reset_points():
    with app.app_context():
        companies = CompanyPoints.query.all()
        for company in companies:
            company.points = 1000
        db.session.commit()
        print("企業のポイントをリセットしました！")

def calculate_points(date, start_time_str, end_time_str, num_areas):
    start_time = datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.strptime(end_time_str, "%H:%M").time()
    if isinstance(date, str):
        weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
    else:
        weekday = date.weekday()
    duration = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)).total_seconds() / 1800
    is_peak_time = (weekday == 0 and start_time < time(12, 0)) or (weekday == 4 and end_time > time(13, 0))
    cost_per_30min = 20 if is_peak_time else 10
    total_cost = int(duration) * cost_per_30min * num_areas
    return max(total_cost, 0)

@app.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if request.method == 'POST':
        try:
            company_name = request.form['company']
            name = request.form['name']
            employee_id = request.form['employee_id']
            areas = request.form.getlist('area')
            date = datetime.strptime(request.form['date'], "%Y-%m-%d").date()
            start_time_str = request.form['start_time']
            end_time_str = request.form['end_time']
            # ケータリング予約情報
            catering_course = request.form.get('catering_course')
            if catering_course == "none" or catering_course == "":
                catering_course = None
                catering_people = None
            else:
                catering_people = request.form.get('catering_people')
                if catering_people:
                    catering_people = int(catering_people)
            # ビール・ワイン予約情報
            beer_count = request.form.get('beer_count')
            beer_count = int(beer_count) if beer_count and beer_count.isdigit() else 0
            wine_sparkling = request.form.get('wine_sparkling')
            wine_sparkling = int(wine_sparkling) if wine_sparkling and wine_sparkling.isdigit() else 0
            wine_white = request.form.get('wine_white')
            wine_white = int(wine_white) if wine_white and wine_white.isdigit() else 0
            wine_red = request.form.get('wine_red')
            wine_red = int(wine_red) if wine_red and wine_red.isdigit() else 0

            start_datetime = datetime.strptime(f"{date} {start_time_str}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{date} {end_time_str}", "%Y-%m-%d %H:%M")
            if start_datetime >= end_datetime:
                return jsonify({"success": False, "message": "終了時間は開始時間より後に設定してください。"}), 400

            area_str = ", ".join(areas)
            all_areas = {"キヅキ", "オチツキ", "シタシミ", "ニギワイ"}
            new_reservation_areas = set(areas)
            existing_reservations = Reservation.query.filter(
                and_(
                    Reservation.date == date,
                    Reservation.start_time < end_time_str,
                    Reservation.end_time > start_time_str
                )
            ).all()
            if "全体貸切" in areas:
                for res in existing_reservations:
                    existing_reserved_areas = set(a.strip() for a in res.area.split(","))
                    if existing_reserved_areas & all_areas or "全体貸切" in existing_reserved_areas:
                        return jsonify({"message": f"エラー: {date} の {start_time_str}〜{end_time_str} はすでに予約されています。"}), 400
            else:
                for res in existing_reservations:
                    existing_reserved_areas = set(a.strip() for a in res.area.split(","))
                    if "全体貸切" in existing_reserved_areas:
                        return jsonify({"message": f"エラー: {date} の {start_time_str}〜{end_time_str} は貸切予約済みのため、予約できません。"}), 400
                    if existing_reserved_areas & new_reservation_areas:
                        return jsonify({"message": f"エラー: {date} の {start_time_str}〜{end_time_str} にすでに予約されているエリアがあります。"}), 400

            company_record = CompanyPoints.query.filter_by(company=company_name).first()
            if not company_record:
                return jsonify({"message": f"エラー: 企業情報が見つかりません（{company_name}）"}), 400
            num_areas = 4 if "全体貸切" in areas else len(areas)
            required_points = calculate_points(date, start_time_str, end_time_str, num_areas)
            if company_record.points < required_points:
                return jsonify({
                    "message": f"エラー: ポイントが不足しています（必要: {required_points}pt, 保有: {company_record.points}pt）"
                }), 400

        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": f"サーバーエラーが発生しました: {str(e)}"}), 500

        try:
            new_reservation = Reservation(
                company=company_name,
                name=name,
                employee_id=employee_id,
                area=area_str,
                date=date,
                start_time=start_time_str,
                end_time=end_time_str,
                catering_course=catering_course,
                catering_people=catering_people,
                beer_count=beer_count,
                wine_sparkling=wine_sparkling,
                wine_white=wine_white,
                wine_red=wine_red
            )
            db.session.add(new_reservation)
            company_record.points -= required_points
            db.session.commit()
            return jsonify(
                success=True,
                message=f"予約完了: {date} の {start_time_str} から {end_time_str} まで {area_str} を予約しました！",
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
    if not date or not start_time or not end_time or not num_areas:
        return jsonify({'error': 'Invalid input'}), 400
    try:
        num_areas = int(num_areas)
    except ValueError:
        return jsonify({'error': 'Invalid num_areas'}), 400
    try:
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        duration_minutes = (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)
        if duration_minutes <= 0:
            return jsonify({'error': 'Invalid time range'}), 400
        time_slots = duration_minutes / 30
        base_points_per_area = 10
        total_points = int(base_points_per_area * num_areas * time_slots)
        return jsonify({'points': total_points})
    except Exception as e:
        return jsonify({'error': 'Calculation error'}), 500

@app.route('/get_company_points', methods=['GET'])
def get_company_points():
    company_name = request.args.get('company')
    if not company_name:
        return jsonify({"error": "企業名が指定されていません"}), 400
    company_record = CompanyPoints.query.filter_by(company=company_name).first()
    if company_record:
        return jsonify({"points": company_record.points})
    else:
        return jsonify({"error": "企業が見つかりません"}), 404

@app.route('/dashboard/<company>')
def dashboard(company):
    reservations = Reservation.query.filter_by(company=company).all()
    points = fetch_company_points(company)
    template_name = f'dashboard-{company}.html'
    return render_template(template_name, company=company, reservations=reservations, points=points)

@app.route('/cancel_reservation/<int:reservation_id>', methods=['POST'])
def cancel_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    db.session.delete(reservation)
    db.session.commit()
    return redirect(url_for('dashboard', company=reservation.company))

def init_db():
    with app.app_context():
        db.create_all()
        print("データベース (reservations.db) が作成されました！")
        if not CompanyPoints.query.first():
            companies = ["A社", "B社", "C社", "D社", "E社", "F社"]
            for name in companies:
                cp = CompanyPoints(company=name, points=1000)
                db.session.add(cp)
            db.session.commit()
            print("企業情報をデータベースに追加しました！")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

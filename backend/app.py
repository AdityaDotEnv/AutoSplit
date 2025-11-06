import os
from datetime import datetime, timedelta
from collections import defaultdict
import traceback

from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS

from models import db, Group, Member, Bill, Item, ItemAssignment
from config import Config
from ocr_parser import image_to_text, extract_lines_with_prices
from nlp_parser import find_total_amount, detect_person_item_relations
from payments import create_stripe_payment_intent, venmo_deeplink, upi_deeplink
from apscheduler.schedulers.background import BackgroundScheduler

# ---------- Setup ----------
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ✅ Global CORS configuration (only one place)
CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
    supports_credentials=True,
    methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------- Extensions ----------
db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# ---------- Health ----------
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# ---------- GROUP CREATION ----------
@app.route('/api/groups', methods=['POST'])
def create_group():
    data = request.json or {}
    name = data.get('name', 'My Group')
    members = data.get('members', [])

    g = Group(name=name)
    db.session.add(g)
    db.session.commit()

    for m in members:
        mem = Member(
            group_id=g.id,
            name=m.get('name'),
            upi_id=m.get('upi_id'),
            venmo_id=m.get('venmo_id'),
        )
        db.session.add(mem)
    db.session.commit()

    return jsonify({'id': g.id, 'name': g.name})

# ---------- GROUP RETRIEVAL ----------
@app.route('/api/groups/<group_id>', methods=['GET'])
def get_group(group_id):
    g = Group.query.get_or_404(group_id)
    return jsonify({
        'id': g.id,
        'name': g.name,
        'members': [
            {'id': m.id, 'name': m.name, 'upi_id': m.upi_id, 'venmo_id': m.venmo_id}
            for m in g.members
        ]
    })

# ---------- BILL UPLOAD ----------
@app.route('/api/upload', methods=['POST'])
def upload_bill():
    try:
        group_id = request.form.get('group_id')
        f = request.files.get('file')

        if not f:
            return jsonify({'error': 'No file uploaded'}), 400

        filename = f"{datetime.utcnow().timestamp()}_{f.filename}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)

        # OCR + NLP pipeline
        text = image_to_text(path)
        items = extract_lines_with_prices(text)
        total = find_total_amount(text)
        parsed_assignments = detect_person_item_relations(items, text)

        bill = Bill(group_id=group_id, raw_text=text, total_amount=total)
        db.session.add(bill)
        db.session.commit()

        for it in items:
            item = Item(bill_id=bill.id, description=it['description'], price=it['price'])
            db.session.add(item)
        db.session.commit()

        return jsonify({
            'bill_id': bill.id,
            'raw_text': text,
            'total': total,
            'items': [{'id': it.id, 'description': it.description, 'price': it.price} for it in bill.items],
            'auto_matches': parsed_assignments
        })

    except Exception as e:
        print("❌ Upload error:", e)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ---------- ITEM ASSIGNMENT (normalize to AMOUNTS ₹) ----------
@app.route('/api/assign', methods=['POST'])
def assign_items():
    try:
        payload = request.json or {}
        raw = payload.get('assignments', [])
        if not isinstance(raw, list):
            return jsonify({'error': 'assignments must be a list'}), 400
        if not raw:
            return jsonify({'status': 'ok', 'assigned': []})

        # Group by item_id (UUID/string-safe)
        per_item = defaultdict(list)
        for a in raw:
            try:
                item_id = str(a['item_id'])
                member_id = str(a['member_id'])
                share = float(a.get('share') or 0.0)
            except (KeyError, ValueError, TypeError):
                return jsonify({'error': f'Bad assignment payload: {a}'}), 400
            per_item[item_id].append({'member_id': member_id, 'share': share})

        results = []

        for item_id, assigns in per_item.items():
            item = Item.query.get(item_id)
            if not item:
                # If an item doesn't exist, skip gracefully
                continue

            # Clear existing to avoid double counting on resave
            db.session.query(ItemAssignment).filter_by(item_id=item_id).delete(synchronize_session=False)
            db.session.flush()

            k = len(assigns)
            price = float(item.price or 0.0)
            provided = [float(a['share']) for a in assigns]
            sum_provided = sum(provided)

            if k == 0 or price <= 0:
                amounts = [0.0] * k

            elif sum_provided == 0.0:
                # nothing provided → equal split
                base = round(price / k, 2)
                amounts = [base] * k
                # rounding fix
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)

            elif sum_provided <= 1.0001:
                # fractions → convert to ₹
                amounts = [round(s * price, 2) for s in provided]
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)

            elif abs(sum_provided - price) <= max(0.02, 0.01 * price):
                # already ₹ that (roughly) sum to price
                amounts = [round(s, 2) for s in provided]
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)

            else:
                # normalize proportionally to match item price
                amounts = [round((s / sum_provided) * price, 2) for s in provided]
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)

            for a, amt in zip(assigns, amounts):
                ia = ItemAssignment(item_id=item_id, member_id=a['member_id'], share=amt)  # store ₹
                db.session.add(ia)
                results.append({'item_id': item_id, 'member_id': a['member_id'], 'share': amt})

        db.session.commit()
        return jsonify({'status': 'ok', 'assigned': results})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ---------- GROUP SUMMARY (sum AMOUNTS) ----------
@app.route('/api/group/<group_id>/summary', methods=['GET'])
def group_summary(group_id):
    g = Group.query.get_or_404(group_id)
    members = {m.id: {'id': m.id, 'name': m.name, 'total_owed': 0.0} for m in g.members}
    bills = Bill.query.filter_by(group_id=group_id).all()

    # ItemAssignment.share is now stored as amount (₹). Just sum.
    for b in bills:
        for it in b.items:
            for a in it.assignments:
                members[a.member_id]['total_owed'] += float(a.share or 0.0)

    for m in members.values():
        m['total_owed'] = round(m['total_owed'], 2)

    return jsonify({'members': list(members.values()), 'bill_count': len(bills)})

# ---------- PAYMENTS ----------
@app.route('/api/pay/upi', methods=['POST'])
def pay_upi():
    data = request.json
    payee_upi = data['upi']
    payee_name = data.get('name', 'Friend')
    amount = float(data['amount'])
    link = upi_deeplink(payee_upi, payee_name, amount)
    return jsonify({'upi_link': link})

@app.route('/api/pay/venmo', methods=['POST'])
def pay_venmo():
    data = request.json
    venmo_id = data['venmo_id']
    amount = float(data['amount'])
    note = data.get('note', 'AutoSplit')
    link = venmo_deeplink(venmo_id, amount, note)
    return jsonify({'venmo_link': link})

@app.route('/api/pay/stripe', methods=['POST'])
def pay_stripe():
    data = request.json
    amount = float(data['amount'])
    desc = data.get('description', 'AutoSplit payment')
    intent = create_stripe_payment_intent(amount, currency='inr', description=desc)
    return jsonify({
        'client_secret': intent.client_secret,
        'stripe_pub': app.config.get('STRIPE_PUBLISHABLE_KEY')
    })

# ---------- SOCKET.IO ----------
@socketio.on('join')
def on_join(data):
    room = data.get('group')
    join_room(room)
    emit('system', {'msg': f"{data.get('user')} joined."}, room=room)

@socketio.on('message')
def handle_message(data):
    room = data.get('group')
    emit('message', data, room=room)

# ---------- Scheduler ----------
def monthly_summary_job():
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=30)
        groups = Group.query.all()
        for g in groups:
            recent_bills = Bill.query.filter(Bill.group_id == g.id, Bill.created_at >= cutoff).all()
            print(f"Monthly summary for group {g.name}: {len(recent_bills)} bills")

scheduler = BackgroundScheduler()
scheduler.add_job(monthly_summary_job, 'interval', days=1)
scheduler.start()

# ---------- Main ----------
if __name__ == '__main__':
    print("🚀 Server running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

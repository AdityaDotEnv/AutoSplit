import os
from flask import Flask, request, jsonify, send_from_directory
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit, join_room
from models import db, Group, Member, Bill, Item, ItemAssignment
from config import Config
from ocr_parser import image_to_text, extract_lines_with_prices
from nlp_parser import find_total_amount, detect_person_item_relations
from payments import create_stripe_payment_intent, venmo_deeplink, upi_deeplink
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/groups', methods=['POST'])
def create_group():
    data = request.json
    name = data.get('name', 'My Group')
    members = data.get('members', [])
    g = Group(name=name)
    db.session.add(g)
    db.session.commit()
    for m in members:
        mem = Member(group_id=g.id, name=m.get('name'), upi_id=m.get('upi_id'), venmo_id=m.get('venmo_id'))
        db.session.add(mem)
    db.session.commit()
    return jsonify({'id': g.id, 'name': g.name})

@app.route('/api/groups/<group_id>', methods=['GET'])
def get_group(group_id):
    g = Group.query.get_or_404(group_id)
    return jsonify({
        'id': g.id,
        'name': g.name,
        'members': [{'id': m.id, 'name': m.name, 'upi_id': m.upi_id, 'venmo_id': m.venmo_id} for m in g.members]
    })

@app.route('/api/upload', methods=['POST'])
def upload_bill():
    group_id = request.form.get('group_id')
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'no file'}), 400
    filename = f"{datetime.utcnow().timestamp()}_{f.filename}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(path)

    text = image_to_text(path)
    items = extract_lines_with_prices(text)
    total = find_total_amount(text)
    parsed_assignments = detect_person_item_relations(items, text)  # dict item_index -> names

    bill = Bill(group_id=group_id, raw_text=text, total_amount=total)
    db.session.add(bill)
    db.session.commit()
    for it in items:
        item = Item(bill_id=bill.id, description=it['description'], price=it['price'])
        db.session.add(item)
    db.session.commit()

    # Prepare response with items and any auto-detected person matches
    return jsonify({
        'bill_id': bill.id,
        'raw_text': text,
        'total': total,
        'items': [{'id': it.id, 'description': it.description, 'price': it.price} for it in bill.items],
        'auto_matches': parsed_assignments
    })

@app.route('/api/assign', methods=['POST'])
def assign_items():
    payload = request.json
    assignments = payload.get('assignments', [])  # list of {item_id, member_id, share}
    results = []
    for a in assignments:
        ia = ItemAssignment(item_id=a['item_id'], member_id=a['member_id'], share=float(a['share']))
        db.session.add(ia)
        results.append({'item_id': a['item_id'], 'member_id': a['member_id'], 'share': a['share']})
    db.session.commit()
    return jsonify({'status':'ok', 'assigned': results})

@app.route('/api/group/<group_id>/summary', methods=['GET'])
def group_summary(group_id):
    # compute outstanding per member
    g = Group.query.get_or_404(group_id)
    members = {m.id: {'id': m.id, 'name': m.name, 'total_owed': 0.0} for m in g.members}
    bills = Bill.query.filter_by(group_id=group_id).all()
    for b in bills:
        for it in b.items:
            for a in it.assignments:
                members[a.member_id]['total_owed'] += a.share
    return jsonify({'members': list(members.values()), 'bill_count': len(bills)})

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
    return jsonify({'client_secret': intent.client_secret, 'stripe_pub': app.config.get('STRIPE_PUBLISHABLE_KEY')})

# Simple chat with Socket.IO
@socketio.on('join')
def on_join(data):
    room = data.get('group')
    join_room(room)
    emit('system', {'msg': f"{data.get('user')} joined."}, room=room)

@socketio.on('message')
def handle_message(data):
    room = data.get('group')
    emit('message', data, room=room)


# Monthly summary job
def monthly_summary_job():
    from models import db, Group, Bill
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=30)
        groups = Group.query.all()
        for g in groups:
            recent_bills = Bill.query.filter(Bill.group_id==g.id, Bill.created_at >= cutoff).all()
            # compute fun insights e.g., most-ordered item, total pizza count heuristics
            # For brevity, send to logs — in production, email/push notifications to group members
            print(f"Monthly summary for group {g.name}: {len(recent_bills)} bills")

scheduler = BackgroundScheduler()
scheduler.add_job(monthly_summary_job, 'interval', days=1)  # run daily, produce monthly summaries
scheduler.start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

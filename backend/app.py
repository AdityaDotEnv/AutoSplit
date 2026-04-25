import os
import traceback
import traceback
from datetime import datetime, timedelta

# Enforce stability flags if needed, but Paddle is removed
from collections import defaultdict
from typing import Optional, List, Dict, Any

from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

from models import db, Group, Member, Bill, Item, ItemAssignment
from config import Config
from ocr_parser import extract_ocr_tokens, group_tokens_into_lines
from receipt_parser import parse_receipt
from reconcile import reconcile
from nlp_parser import detect_person_item_relations
from intelligent_parser import refine_with_gemini
from payments import create_stripe_payment_intent, venmo_deeplink, upi_deeplink


UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config.from_object(Config)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

CORS(
    app,
    resources={
        r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}
    },
    supports_credentials=True,
    methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

db.init_app(app)
migrate = Migrate(app, db)
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    logger=True,
    engineio_logger=True,
)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/groups", methods=["POST"])
def create_group():
    data = request.json or {}
    name = data.get("name", "My Group")
    members = data.get("members", [])

    if not name or not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Invalid group name"}), 400

    g = Group(name=name.strip())
    db.session.add(g)
    db.session.commit()

    for m in members:
        mem_name = m.get("name")
        if not mem_name or not isinstance(mem_name, str) or not mem_name.strip():
            continue
        mem = Member(
            group_id=g.id,
            name=mem_name.strip(),
            upi_id=m.get("upi_id"),
            venmo_id=m.get("venmo_id"),
        )
        db.session.add(mem)
    db.session.commit()

    return jsonify({"id": g.id, "name": g.name})


@app.route("/api/groups/<group_id>", methods=["GET"])
def get_group(group_id):
    g = Group.query.get_or_404(group_id)
    return jsonify(
        {
            "id": g.id,
            "name": g.name,
            "members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "upi_id": m.upi_id,
                    "venmo_id": m.venmo_id,
                }
                for m in g.members
            ],
        }
    )


@app.route("/api/upload", methods=["POST"])
def upload_bill():
    try:
        group_id = request.form.get("group_id")
        f = request.files.get("file")

        if not f:
            return jsonify({"error": "No file uploaded"}), 400

        filename = f"{datetime.utcnow().timestamp()}_{f.filename}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        f.save(path)

        ocr_tokens = extract_ocr_tokens(path)
        if not ocr_tokens:
            print(f"OCR Failed for {filename}. No text detected.")
            return jsonify(
                {
                    "error": "OCR failed",
                    "details": "No text detected",
                }
            ), 422

        lines = group_tokens_into_lines(ocr_tokens)
        parsed_receipt = parse_receipt(lines)
        recon = reconcile(parsed_receipt)

        raw_text = "\n".join(l['text'] for l in lines)
        total_amount = recon['calculated_total'] if recon['stated_total'] is None else recon['stated_total']

        items_for_db = []
        if not recon['reconciled']:
            print("Reconciliation failed, falling back to Gemini repair")
            # Try intelligent refinement
            refined_bill = refine_with_gemini(raw_text)
            
            if refined_bill and refined_bill.items:
                print("Using Gemini-refined bill items")
                # Blocked keywords for item extraction
                BLOCKED = {
                    "subtotal", "sub total", "gst", "cgst", "sgst",
                    "tax", "service charge", "staff contribution",
                    "round off", "total", "invoice value", "total qty"
                }

                for idx, git in enumerate(refined_bill.items):
                    derived_name = (git.name or "").strip() or (git.raw_text or "").strip()
                    
                    if not derived_name or derived_name.lower() in {"item", "(item)", "unknown"}:
                        derived_name = f"Unparsed Item {idx+1}"

                    if derived_name.lower() in BLOCKED:
                        continue

                    items_for_db.append({
                        "description": derived_name,
                        "price": git.amount,
                        "is_valid": True,
                        "raw_line": git.raw_text or derived_name,
                        "validation_errors": []
                    })
                
                if refined_bill.totals and refined_bill.totals.grand_total:
                    total_amount = refined_bill.totals.grand_total
        
        if not items_for_db:
            # Use deterministic parser result
            for item in parsed_receipt.items:
                if item.amount is not None:
                    items_for_db.append({
                        "description": item.name,
                        "price": item.amount,
                        "is_valid": True,
                        "raw_line": item.name,
                        "validation_errors": []
                    })

        item_dicts = [
            {"description": it["description"], "price": it["price"], "raw_line": it["raw_line"]}
            for it in items_for_db
        ]
        parsed_assignments = detect_person_item_relations(item_dicts, raw_text)

        bill = Bill(group_id=group_id, raw_text=raw_text, total_amount=total_amount)
        db.session.add(bill)
        db.session.commit()

        db_items = []
        valid_item_count = 0
        for it in items_for_db:
            item = Item(bill_id=bill.id, description=it["description"], price=it["price"])
            db.session.add(item)
            db.session.flush()
            db_items.append(item)
            valid_item_count += 1

        db.session.commit()

        return jsonify(
            {
                "bill_id": bill.id,
                "raw_text": raw_text,
                "total": total_amount,
                "total_valid": True,
                "total_error": None,
                "items": [
                    {
                        "id": db_item.id if db_item else None,
                        "description": it["description"],
                        "price": it["price"],
                        "is_valid": it["is_valid"],
                        "validation_errors": it["validation_errors"],
                    }
                    for it, db_item in zip(items_for_db, db_items)
                ],
                "valid_item_count": valid_item_count,
                "auto_matches": parsed_assignments,
            }
        )

    except Exception as e:
        print("Upload error:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        if 'path' in locals() and os.path.exists(path):
            try:
                os.remove(path)
                print(f"Cleaned up {path}")
            except Exception as e:
                print(f"Failed to cleanup {path}: {e}")


@app.route("/api/assign", methods=["POST"])
def assign_items():
    try:
        payload = request.json or {}
        raw = payload.get("assignments", [])
        if not isinstance(raw, list):
            return jsonify({"error": "assignments must be a list"}), 400
        if not raw:
            return jsonify({"status": "ok", "assigned": []})

        per_item = defaultdict(list)
        for a in raw:
            item_id = a.get("item_id")
            member_id = a.get("member_id")
            share = a.get("share")

            if not item_id or not isinstance(item_id, str):
                continue
            if not member_id or not isinstance(member_id, str):
                continue
            if share is None:
                continue

            try:
                share = float(share)
                if share < 0:
                    continue
            except (ValueError, TypeError):
                continue

            per_item[item_id].append({"member_id": member_id, "share": share})

        results = []
        for item_id, assigns in per_item.items():
            item = Item.query.get(item_id)
            if not item:
                continue

            db.session.query(ItemAssignment).filter_by(item_id=item_id).delete(
                synchronize_session=False
            )
            db.session.flush()

            k = len(assigns)
            price = float(item.price or 0.0)
            provided = [float(a["share"]) for a in assigns]
            sum_provided = sum(provided)

            if k == 0 or price <= 0:
                amounts = [0.0] * k
            elif sum_provided == 0.0:
                base = round(price / k, 2)
                amounts = [base] * k
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)
            elif sum_provided <= 1.0001:
                amounts = [round(s * price, 2) for s in provided]
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)
            elif abs(sum_provided - price) <= max(0.02, 0.01 * price):
                amounts = [round(s, 2) for s in provided]
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)
            else:
                amounts = [round((s / sum_provided) * price, 2) for s in provided]
                diff = round(price - sum(amounts), 2)
                if amounts and abs(diff) >= 0.01:
                    amounts[0] = round(amounts[0] + diff, 2)

            for a, amt in zip(assigns, amounts):
                ia = ItemAssignment(
                    item_id=item_id, member_id=a["member_id"], share=amt
                )
                db.session.add(ia)
                results.append(
                    {"item_id": item_id, "member_id": a["member_id"], "share": amt}
                )

        db.session.commit()
        return jsonify({"status": "ok", "assigned": results})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/group/<group_id>/summary", methods=["GET"])
def group_summary(group_id):
    g = Group.query.get_or_404(group_id)
    members = {m.id: {"id": m.id, "name": m.name, "total_owed": 0.0} for m in g.members}
    bills = Bill.query.filter_by(group_id=group_id).all()

    for b in bills:
        for it in b.items:
            for a in it.assignments:
                members[a.member_id]["total_owed"] += float(a.share or 0.0)

    for m in members.values():
        m["total_owed"] = round(m["total_owed"], 2)

    return jsonify({"members": list(members.values()), "bill_count": len(bills)})


@app.route("/api/pay/upi", methods=["POST"])
def pay_upi():
    data = request.json or {}
    payee_upi = data.get("upi")
    payee_name = data.get("name", "Friend")
    amount = data.get("amount")

    if not payee_upi or not isinstance(payee_upi, str):
        return jsonify({"error": "Missing or invalid upi_id"}), 400
    if amount is None:
        return jsonify({"error": "Missing amount"}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    link = upi_deeplink(payee_upi, payee_name, amount)
    return jsonify({"upi_link": link})


@app.route("/api/pay/venmo", methods=["POST"])
def pay_venmo():
    data = request.json or {}
    venmo_id = data.get("venmo_id")
    amount = data.get("amount")
    note = data.get("note", "AutoSplit")

    if not venmo_id or not isinstance(venmo_id, str):
        return jsonify({"error": "Missing or invalid venmo_id"}), 400
    if amount is None:
        return jsonify({"error": "Missing amount"}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    link = venmo_deeplink(venmo_id, amount, note)
    return jsonify({"venmo_link": link})


@app.route("/api/pay/stripe", methods=["POST"])
def pay_stripe():
    data = request.json or {}
    amount = data.get("amount")
    desc = data.get("description", "AutoSplit payment")

    if amount is None:
        return jsonify({"error": "Missing amount"}), 400

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    intent = create_stripe_payment_intent(amount, currency="inr", description=desc)
    return jsonify(
        {
            "client_secret": intent.client_secret,
            "stripe_pub": app.config.get("STRIPE_PUBLISHABLE_KEY"),
        }
    )


@socketio.on("join")
def on_join(data):
    room = data.get("group")
    join_room(room)
    emit("system", {"msg": f"{data.get('user')} joined."}, room=room)


@socketio.on("message")
def handle_message(data):
    room = data.get("group")
    emit("message", data, room=room)


def monthly_summary_job():
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=30)
        groups = Group.query.all()
        for g in groups:
            recent_bills = Bill.query.filter(
                Bill.group_id == g.id, Bill.created_at >= cutoff
            ).all()
            print(f"Monthly summary for group {g.name}: {len(recent_bills)} bills")


scheduler = BackgroundScheduler()
scheduler.add_job(monthly_summary_job, "interval", days=1)
scheduler.start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server running at http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=True)

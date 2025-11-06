from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

def gen_uuid():
    return str(uuid.uuid4())

class Group(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    name = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    members = db.relationship('Member', backref='group', cascade="all, delete-orphan")

class Member(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    group_id = db.Column(db.String, db.ForeignKey('group.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    upi_id = db.Column(db.String, nullable=True)
    venmo_id = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('ItemAssignment', backref='member', cascade="all, delete-orphan")

class Bill(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    group_id = db.Column(db.String, db.ForeignKey('group.id'), nullable=True)
    raw_text = db.Column(db.Text, nullable=True)
    total_amount = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('Item', backref='bill', cascade="all, delete-orphan")

class Item(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    bill_id = db.Column(db.String, db.ForeignKey('bill.id'), nullable=False)
    description = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    assignments = db.relationship('ItemAssignment', backref='item', cascade="all, delete-orphan")

class ItemAssignment(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    item_id = db.Column(db.String, db.ForeignKey('item.id'), nullable=False)
    member_id = db.Column(db.String, db.ForeignKey('member.id'), nullable=False)
    share = db.Column(db.Float, nullable=False)  # how much this member owes for the item

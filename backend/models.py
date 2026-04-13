from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Any
from uuid import uuid4
import re

db = SQLAlchemy()


def gen_uuid() -> str:
    return str(uuid4())


class Group(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    name = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    members = db.relationship("Member", backref="group", cascade="all, delete-orphan")


class Member(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    group_id = db.Column(db.String, db.ForeignKey("group.id"), nullable=False)
    name = db.Column(db.String, nullable=False)
    upi_id = db.Column(db.String, nullable=True)
    venmo_id = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship(
        "ItemAssignment", backref="member", cascade="all, delete-orphan"
    )


class Bill(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    group_id = db.Column(db.String, db.ForeignKey("group.id"), nullable=True)
    raw_text = db.Column(db.Text, nullable=True)
    total_amount = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("Item", backref="bill", cascade="all, delete-orphan")


class Item(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    bill_id = db.Column(db.String, db.ForeignKey("bill.id"), nullable=False)
    description = db.Column(db.String, nullable=False)
    price = db.Column(db.Float, nullable=False)
    assignments = db.relationship(
        "ItemAssignment", backref="item", cascade="all, delete-orphan"
    )


class ItemAssignment(db.Model):
    id = db.Column(db.String, primary_key=True, default=gen_uuid)
    item_id = db.Column(db.String, db.ForeignKey("item.id"), nullable=False)
    member_id = db.Column(db.String, db.ForeignKey("member.id"), nullable=False)
    share = db.Column(db.Float, nullable=False)


@dataclass
class ValidatedItem:
    """Schema-validated item extracted from OCR with null safety."""

    description: str = "(item)"
    price: Optional[float] = None
    raw_line: str = ""
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ValidatedItem":
        """Create validated item from raw dict with strict validation."""
        errors = []
        desc = data.get("description") if data.get("description") is not None else ""
        price = data.get("price")
        raw = data.get("raw_line") if data.get("raw_line") is not None else ""

        if not desc or not desc.strip():
            desc = "(item)"
        else:
            desc = cls._validate_description(desc)
            if not desc:
                errors.append("Invalid description after sanitization")

        if price is None:
            errors.append("Price is None/unavailable")
        else:
            price = cls._validate_price(price)
            if price is None:
                errors.append("Invalid price value")
            elif price <= 0 or price > 1000000:
                errors.append("Price out of valid range (0-1000000)")

        is_valid = len(errors) == 0 and price is not None
        return cls(
            description=desc,
            price=price,
            raw_line=raw,
            is_valid=is_valid,
            validation_errors=errors,
        )

    @staticmethod
    def _validate_description(desc: str) -> Optional[str]:
        if not desc or not isinstance(desc, str):
            return None
        s = desc.strip()
        s = re.sub(r"^[\s\$\€\₹\£]+", "", s)
        s = re.sub(r"^\d+[\.\)\-]\s*", "", s)
        s = s.strip()
        if len(s) < 1:
            return None
        return s if len(s) <= 500 else s[:500]

    @staticmethod
    def _validate_price(price: Any) -> Optional[float]:
        if price is None:
            return None
        try:
            val = float(price)
            if val <= 0 or val > 1000000:
                return None
            return round(val, 2)
        except (TypeError, ValueError):
            return None


@dataclass
class ValidatedTotal:
    """Schema-validated total amount with null safety."""

    amount: Optional[float] = None
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    source: str = ""

    @classmethod
    def from_value(cls, value: Any, source: str = "inferred") -> "ValidatedTotal":
        errors = []
        amount = None

        if value is None:
            errors.append("Total amount is None/unavailable")
        else:
            amount = ValidatedItem._validate_price(value)
            if amount is None:
                errors.append("Invalid total value")

        is_valid = len(errors) == 0 and amount is not None and amount >= 0
        return cls(
            amount=amount, is_valid=is_valid, validation_errors=errors, source=source
        )


@dataclass
class ValidatedAssignment:
    """Schema-validated item assignment with null safety."""

    item_id: Optional[str] = None
    member_id: Optional[str] = None
    share: Optional[float] = None
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ValidatedAssignment":
        errors = []
        item_id = data.get("item_id")
        member_id = data.get("member_id")
        share = data.get("share")

        if not item_id or not isinstance(item_id, str) or not item_id.strip():
            errors.append("Missing or invalid item_id")

        if not member_id or not isinstance(member_id, str) or not member_id.strip():
            errors.append("Missing or invalid member_id")

        if share is None:
            errors.append("Missing share value")
        else:
            share = ValidatedItem._validate_price(share)
            if share is None or share < 0:
                errors.append("Invalid share value")

        is_valid = len(errors) == 0 and share is not None
        return cls(
            item_id=item_id,
            member_id=member_id,
            share=share,
            is_valid=is_valid,
            validation_errors=errors,
        )


@dataclass
class ParsedBillResult:
    """Complete parsed bill result with validation status."""

    raw_text: str = ""
    items: List[ValidatedItem] = field(default_factory=list)
    total: Optional[ValidatedTotal] = None
    auto_assignments: dict = field(default_factory=dict)
    parsing_errors: List[str] = field(default_factory=list)
    is_fully_valid: bool = False

    @property
    def valid_items(self) -> List[ValidatedItem]:
        return [it for it in self.items if it.is_valid]

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def valid_item_count(self) -> int:
        return len(self.valid_items)

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text or "",
            "items": [
                {
                    "description": it.description,
                    "price": it.price,
                    "raw_line": it.raw_line,
                    "is_valid": it.is_valid,
                    "validation_errors": it.validation_errors,
                }
                for it in self.items
            ],
            "valid_items": [
                {"description": it.description, "price": it.price}
                for it in self.valid_items
            ],
            "total": {
                "amount": self.total.amount if self.total else None,
                "is_valid": self.total.is_valid if self.total else False,
                "source": self.total.source if self.total else "",
            },
            "auto_assignments": self.auto_assignments,
            "parsing_errors": self.parsing_errors,
            "is_fully_valid": self.is_fully_valid,
            "item_count": self.item_count,
            "valid_item_count": self.valid_item_count,
        }

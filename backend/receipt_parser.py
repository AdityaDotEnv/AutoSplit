import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from rapidfuzz import fuzz

@dataclass
class LineItem:
    name: str
    quantity: Optional[int]
    unit_price: Optional[float]
    amount: float

@dataclass
class Charge:
    label: str
    amount: float
    category: str

@dataclass
class Receipt:
    items: List[LineItem] = field(default_factory=list)
    shared_charges: List[Charge] = field(default_factory=list)
    taxes: List[Charge] = field(default_factory=list)
    totals: Dict[str, float] = field(default_factory=dict)

NON_ITEM_BLOCKLIST = [
    "subtotal", "gst", "cgst", "sgst", "tax", "service charge",
    "staff contribution", "round off", "total", "invoice value", "amount due"
]

def clean_number(text: str) -> Optional[float]:
    # Support negative numbers and typical float formats
    s = text.strip()
    s = re.sub(r'[^\d\.,\-]', '', s)
    if not s: return None
    
    # Handle European format vs US format
    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif has_comma and not has_dot:
        parts = s.split(",")
        if len(parts[-1]) == 2:
            s = s.replace(",", ".")
        elif len(parts[-1]) == 3 and len(parts) > 1:
            s = "".join(parts)
        else:
            s = s.replace(",", ".")
            
    try:
        return float(s)
    except:
        return None

def is_blocked(text: str) -> bool:
    lower_text = text.lower().strip()
    if not lower_text: return False
    
    for b in NON_ITEM_BLOCKLIST:
        if b in lower_text:
            return True
        # Use ratio instead of partial_ratio to avoid short words matching longer blocked words
        if fuzz.ratio(lower_text, b) > 80:
            return True
            
    return False

def categorize_charge(label: str) -> str:
    lbl = label.lower()
    if 'tax' in lbl or 'gst' in lbl or 'vat' in lbl:
        return 'tax'
    return 'shared'

HEADER_KEYWORDS = ["invoice", "bill", "date", "time", "order", "table", "guest", "cashier"]

def is_header_metadata(text: str) -> bool:
    lower_text = text.lower()
    for kw in HEADER_KEYWORDS:
        if kw in lower_text:
            return True
    return False

def parse_receipt(lines: List[Dict[str, Any]]) -> Receipt:
    state = "header"
    receipt = Receipt()
    pending_name_buffer = []

    for line in lines:
        text = line['text']
        tokens = line['tokens']
        lower_text = text.lower()
        
        # State transitions
        if state == "header":
            if "item" in lower_text or "qty" in lower_text or "amt" in lower_text or "amount" in lower_text:
                state = "items"
                pending_name_buffer.clear() # Clear any header garbage
                continue
                
        if "subtotal" in lower_text or "sub total" in lower_text:
            if state in ["header", "items"]:
                state = "charges"
                
        if state in ["charges", "totals"] and "total" in lower_text and "subtotal" not in lower_text:
            state = "totals"

        # Find amount and qty
        num_tokens = []
        for i, tok in enumerate(tokens):
            val = clean_number(tok['text'])
            if val is not None and re.search(r'\d', tok['text']):
                # Ignore numbers starting with # for amounts
                if not tok['text'].strip().startswith('#'):
                    num_tokens.append((i, tok, val))

        amount = None
        qty = None
        amt_idx = -1
        
        if num_tokens:
            amt_idx, amt_tok, amount = num_tokens[-1]
            if len(num_tokens) > 1:
                qty_idx, qty_tok, qty_val = num_tokens[-2]
                if qty_idx == amt_idx - 1:
                    if qty_val.is_integer() and 0 < qty_val < 1000:
                        qty = int(qty_val)

        if amount is not None:
            text_limit_idx = amt_idx if qty is None else (amt_idx - 1)
            text_tokens = tokens[:text_limit_idx]
        else:
            text_tokens = tokens
            
        text_part = " ".join(t['text'] for t in text_tokens).strip()
        text_part = re.sub(r"^[\s\$\€\₹\£]+", "", text_part).strip()
        text_part = re.sub(r"^\d+[\.\)\-]\s*", "", text_part).strip()

        if is_blocked(text_part):
            if state in ["header", "items"]:
                state = "charges"
                
        if state == "header" and amount is not None:
            if is_header_metadata(text) or is_header_metadata(text_part):
                # Ignore this line's amount, it's just metadata
                amount = None

        if state in ["header", "items"]:
            if amount is None:
                if re.search(r'[A-Za-z]', text_part) and not is_blocked(text_part):
                    # To avoid buffering entire header, only keep last 2 lines max
                    pending_name_buffer.append(text_part)
                    if len(pending_name_buffer) > 2:
                        pending_name_buffer.pop(0)
            else:
                has_alpha = re.search(r'[A-Za-z]', text_part)
                if not has_alpha and not pending_name_buffer:
                    pending_name_buffer.clear()
                    continue
                
                if is_blocked(text_part):
                    state = "charges"
                else:
                    state = "items" # implicitly move to items
                    name_parts = pending_name_buffer + ([text_part] if text_part else [])
                    name = " ".join(name_parts).strip()
                    pending_name_buffer.clear()
                    
                    unit_price = None
                    if qty is not None and qty > 0:
                        unit_price = round(amount / qty, 2)
                        
                    receipt.items.append(LineItem(
                        name=name,
                        quantity=qty,
                        unit_price=unit_price,
                        amount=amount
                    ))
                    
        if state in ["charges", "totals"]:
            if amount is not None and text_part and is_blocked(text_part):
                # Classify the charge
                if "total" in text_part.lower() and "subtotal" not in text_part.lower() and "qty" not in text_part.lower():
                    state = "totals"
                    # In case multiple totals are found, we keep the last/largest one usually, but let's just set it
                    receipt.totals['grand_total'] = amount
                elif "subtotal" in text_part.lower():
                    receipt.totals['subtotal'] = amount
                elif "round" in text_part.lower():
                    receipt.shared_charges.append(Charge(label=text_part, amount=amount, category="shared"))
                else:
                    cat = categorize_charge(text_part)
                    charge = Charge(label=text_part, amount=amount, category=cat)
                    if cat == 'tax':
                        receipt.taxes.append(charge)
                    else:
                        receipt.shared_charges.append(charge)

    return receipt

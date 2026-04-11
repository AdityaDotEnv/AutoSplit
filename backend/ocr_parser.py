from PIL import Image
import os
import re
import cv2
import numpy as np
from paddleocr import PaddleOCR

_METADATA_KEYWORDS = [
    "invoice",
    "invoice no",
    "invoice#",
    "bill no",
    "bill#",
    "date",
    "time",
    "gst",
    "tax",
    "subtotal",
    "total due",
    "amount due",
    "amount",
    "phone",
    "tel",
    "mobile",
    "order no",
    "order#",
    "qty",
    "quantity",
    "id",
    "cash",
    "card",
    "paid",
    "change",
    "receipt",
    "taxable",
    "vat",
    "tin",
    "gstin",
    "merchant",
    "address",
    "email",
]

_NUM_TOKEN_RE = re.compile(
    r"(?P<sym>₹|\$|€|Rs\.?|INR)?\s*(?P<num>[0-9][0-9\.,]{0,20}[0-9])"
)
_RIGHTMOST_NUM_RE = re.compile(r"([0-9][0-9\.,]{0,20}[0-9])\s*$")

_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)
    return _ocr


def _is_metadata_line(line):
    low = line.lower()
    for k in _METADATA_KEYWORDS:
        if k in low:
            return True
    if re.search(r"[/\\\-]{1,}", line) and re.search(r"\d", line):
        return True
    if re.search(r"\d{8,}", line):
        return True
    return False


def _normalize_number_token(tok, context_numbers=None):
    if not tok or not re.search(r"\d", tok):
        return None

    s = tok.strip()
    s = re.sub(r"[^\d,.\-]", "", s)

    if "." in s and "," in s:
        if s.rfind(".") > s.rfind(","):
            dec = "."
            thou = ","
        else:
            dec = ","
            thou = "."
        s = s.replace(thou, "")
        s = s.replace(dec, ".")
    else:
        if "," in s and "." not in s:
            parts = s.split(",")
            if len(parts[-1]) == 2:
                s = s.replace(",", ".")
            elif len(parts[-1]) == 3 and len(parts) > 1:
                s = "".join(parts)
            else:
                s = s.replace(",", ".")
        elif "." in s and "," not in s:
            parts = s.split(".")
            if len(parts[-1]) <= 2:
                pass
            else:
                s = "".join(parts)

    s = s.strip(".")
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        s = re.sub(r"[^\d\.]", "", s)
    if not s:
        return None

    if "." in s:
        try:
            return float(s)
        except:
            return None

    try:
        val = int(s)
    except:
        return None

    length = len(s)
    if length <= 3:
        return float(val)
    if context_numbers:
        if any(
            isinstance(x, float) and not float(x).is_integer() for x in context_numbers
        ):
            return float(val) / 100.0
    if length >= 5:
        return float(val) / 100.0

    return float(val)


def image_to_text(image_path, psm=None, oem=None):
    """
    Load image and run PaddleOCR with preprocessing.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            img = Image.open(image_path)
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        denoised = cv2.fastNlMeansDenoising(
            gray, None, h=10, templateWindowSize=7, searchWindowSize=21
        )

        ocr = _get_ocr()
        result = ocr.ocr(denoised, cls=True)

        if not result or not result[0]:
            return ""

        lines = []
        for line in result[0]:
            if line and len(line) >= 2:
                text = (
                    line[1][0]
                    if isinstance(line[1], tuple)
                    else line[1].get("text", "")
                )
                if text:
                    lines.append(text)

        return "\n".join(lines)
    except Exception as e:
        print("OCR Error:", e)
        return ""


def extract_lines_with_prices(raw_text):
    """
    Parse raw OCR text and extract item-like lines + prices.
    Returns list of dicts: {'description': str, 'price': float, 'raw_line': str}
    """
    if not raw_text:
        return []

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    results = []

    context_number_tokens = []
    for ln in lines:
        for m in _NUM_TOKEN_RE.finditer(ln):
            tok = m.group("num")
            cleaned = tok.replace(" ", "")
            cleaned = cleaned.replace("₹", "").replace("Rs", "").replace("INR", "")
            if "," in cleaned and "." in cleaned:
                if cleaned.rfind(".") > cleaned.rfind(","):
                    cleaned = cleaned.replace(",", "")
                else:
                    cleaned = cleaned.replace(".", "")
                    cleaned = cleaned.replace(",", ".")
            context_number_tokens.append(cleaned)

    context_numbers = []
    for t in context_number_tokens:
        if "." in t:
            try:
                context_numbers.append(float(t.replace(",", "")))
            except:
                pass

    for ln in lines:
        if _is_metadata_line(ln):
            continue

        m_right = _RIGHTMOST_NUM_RE.search(ln)
        chosen = None
        if m_right:
            chosen = m_right.group(1)
        else:
            m_any = _NUM_TOKEN_RE.search(ln)
            if m_any:
                chosen = m_any.group("num")

        if not chosen:
            continue

        price = _normalize_number_token(chosen, context_numbers or None)
        if price is None:
            continue

        desc = re.sub(re.escape(chosen) + r"\s*$", "", ln).strip()
        desc = re.sub(r"^[\s\$\€\₹\£]+", "", desc).strip()
        desc = re.sub(r"^\d+[\.\)\-]\s*", "", desc).strip()

        if price <= 0 or price > 1000000:
            continue

        results.append(
            {
                "description": desc if desc else "(item)",
                "price": round(price, 2),
                "raw_line": ln,
            }
        )

    return results

from PIL import Image, ImageFilter, ImageOps
import os
import pytesseract
import re
import math

# Use environment variable if present (Docker/Linux)
pytesseract.pytesseract.tesseract_cmd = os.environ.get(
    "TESSERACT_CMD",
    pytesseract.pytesseract.tesseract_cmd
)

# 🪟 Optional fallback for local Windows dev only
# (comment this out or leave as-is if you still run locally on Windows)
# LOCAL_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# if os.path.exists(LOCAL_TESSERACT_PATH):
#     pytesseract.pytesseract.tesseract_cmd = LOCAL_TESSERACT_PATH
# else:
#     print("⚠️ Warning: Tesseract executable not found locally — using default or Docker path")

# Heuristics: keywords that indicate a line is metadata (not an item line)
_METADATA_KEYWORDS = [
    "invoice", "invoice no", "invoice#", "bill no", "bill#", "date", "time",
    "gst", "tax", "subtotal", "total due", "amount due", "amount", "phone",
    "tel", "mobile", "order no", "order#", "qty", "quantity", "id", "cash",
    "card", "paid", "change", "receipt", "taxable", "vat", "tin", "gstin",
    "merchant", "address", "email"
]

# Flexible regex to find monetary-like tokens. We allow dots and commas and optional currency sign.
_NUM_TOKEN_RE = re.compile(r'(?P<sym>₹|\$|€|Rs\.?|INR)?\s*(?P<num>[0-9][0-9\.,]{0,20}[0-9])')

# Price candidate at line end (rightmost number is usually price)
_RIGHTMOST_NUM_RE = re.compile(r'([0-9][0-9\.,]{0,20}[0-9])\s*$')

# Helper: check line for metadata-like markers
def _is_metadata_line(line):
    low = line.lower()
    for k in _METADATA_KEYWORDS:
        if k in low:
            return True
    # if line contains many non-alphanumeric chars or slashes (likely date) treat as metadata
    if re.search(r'[/\\\-]{1,}', line) and re.search(r'\d', line):
        # lines like 12/11/2025 or 2025-11-06 are dates -> metadata
        return True
    # long sequences of digits (>=8) likely phone, gst, invoice ids
    if re.search(r'\d{8,}', line):
        return True
    return False

def _normalize_number_token(tok, context_numbers=None):
    """
    Normalize the numeric token string to a float value.
    - Handles comma/dot decimal separators and common thousand separators.
    - If tok contains both '.' and ',' we infer thousand/decimal based on last separator.
    - If tok has no decimal marker and is long (>4 digits), can optionally treat last 2 digits as cents
      if context_numbers indicates other numbers in the receipt use decimals.
    Returns float or None on failure.
    """
    if not tok or not re.search(r'\d', tok):
        return None

    s = tok.strip()
    # Remove currency symbol and spaces
    s = re.sub(r'[^\d,.\-]', '', s)

    # If s contains both '.' and ',', decide which is decimal:
    if '.' in s and ',' in s:
        # whichever appears last is the decimal separator in many locales
        if s.rfind('.') > s.rfind(','):
            dec = '.'
            thou = ','
        else:
            dec = ','
            thou = '.'
        s = s.replace(thou, '')
        s = s.replace(dec, '.')
    else:
        # Only one of them (or none)
        # If comma used and there are exactly 3 digits after comma, it's probably thousand sep (e.g., 1,234)
        if ',' in s and '.' not in s:
            parts = s.split(',')
            if len(parts[-1]) == 2:
                # treat comma as decimal
                s = s.replace(',', '.')
            elif len(parts[-1]) == 3 and len(parts) > 1:
                # likely thousand separators
                s = ''.join(parts)
            else:
                # ambiguous: prefer comma as decimal only if last part length == 2
                s = s.replace(',', '.')
        # If only '.' present, assume standard decimal if last part length <= 2 else thousand separators
        elif '.' in s and ',' not in s:
            parts = s.split('.')
            if len(parts[-1]) <= 2:
                # decimal point
                pass
            else:
                # could be thousand separators (e.g., 1.234.567) -> remove all dots
                s = ''.join(parts)

    # Now s should look like digits with optional single '.' decimal
    s = s.strip('.')
    if not re.fullmatch(r'\d+(\.\d+)?', s):
        # fallback: remove anything unexpected
        s = re.sub(r'[^\d\.]', '', s)
    if not s:
        return None

    # If there's a decimal point, parse directly
    if '.' in s:
        try:
            return float(s)
        except:
            return None

    # No explicit decimal point: decide if it needs dividing by 100
    try:
        val = int(s)
    except:
        return None

    # Conservative heuristics:
    # - If length <= 3, treat as integer (e.g., 250 -> 250.00)
    # - If length == 4: ambiguous (e.g., 1809 could be 18.09 or 1809); prefer integer unless context suggests decimals
    # - If length >=5: often OCR dropped the decimal; consider /100 if context_numbers shows decimals elsewhere
    length = len(s)
    if length <= 3:
        return float(val)
    # If context_numbers (list of floats or tokens) suggests decimal usage (some tokens had decimals), allow /100
    if context_numbers:
        # if any nearby token had decimals (i.e., floating values), lenient conversion
        if any(isinstance(x, float) and not float(x).is_integer() for x in context_numbers):
            return float(val) / 100.0
    # else, only do auto /100 when very long (>=5 digits) - heuristic for 18099 -> 180.99
    if length >= 5:
        return float(val) / 100.0

    # default fallback: keep as integer value
    return float(val)


def image_to_text(image_path, psm=6, oem=3):
    """
    Load image and run Tesseract OCR with lightweight preprocessing.
    psm = page segmentation mode: default 6 (assume a single uniform block of text)
    """
    try:
        img = Image.open(image_path)

        # Convert to grayscale, increase contrast, and apply adaptive threshold
        # to handle photos and scanned receipts similarly.
        img = img.convert("L")
        img = img.filter(ImageFilter.SHARPEN)
        # Adaptive threshold-ish using point (simple): scale to 0/255 based on mid value
        width, height = img.size
        # Downscale then upscale can remove noise; do small smoothing instead of heavy operations
        img = ImageOps.autocontrast(img)
        # Save memory: do not resize large images drastically (leave Tesseract to handle)
        text = pytesseract.image_to_string(img, lang='eng', config=f'--oem {oem} --psm {psm}')
        return text
    except Exception as e:
        print("❌ OCR Error:", e)
        return ""


def extract_lines_with_prices(raw_text):
    """
    Parse raw OCR text and extract item-like lines + prices.
    Returns list of dicts: {'description': str, 'price': float, 'raw_line': str}
    """
    if not raw_text:
        return []

    # split and keep non-empty lines
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    results = []

    # Pre-scan to see if any explicit decimal tokens exist on receipt ->
    # used by _normalize_number_token to decide auto /100 behaviour
    context_number_tokens = []
    for ln in lines:
        for m in _NUM_TOKEN_RE.finditer(ln):
            tok = m.group('num')
            # quick normalize attempt for context (do not apply /100 here)
            cleaned = tok.replace(' ', '')
            cleaned = cleaned.replace('₹', '').replace('Rs', '').replace('INR', '')
            if ',' in cleaned and '.' in cleaned:
                # normalize last separator as decimal if ambiguous
                if cleaned.rfind('.') > cleaned.rfind(','):
                    cleaned = cleaned.replace(',', '')
                else:
                    cleaned = cleaned.replace('.', '')
                    cleaned = cleaned.replace(',', '.')
            context_number_tokens.append(cleaned)

    # Convert context tokens to floats where obviously decimals exist
    context_numbers = []
    for t in context_number_tokens:
        if '.' in t:
            try:
                context_numbers.append(float(t.replace(',', '')))
            except:
                pass

    for ln in lines:
        # skip metadata lines early (dates, invoice ids, phone numbers)
        if _is_metadata_line(ln):
            continue

        # prefer the rightmost numeric token in the line (prices are usually to the right)
        m_right = _RIGHTMOST_NUM_RE.search(ln)
        chosen = None
        if m_right:
            chosen = m_right.group(1)
        else:
            # fallback: first numeric token
            m_any = _NUM_TOKEN_RE.search(ln)
            if m_any:
                chosen = m_any.group('num')

        if not chosen:
            continue

        # normalize chosen token to float using conservative heuristics
        price = _normalize_number_token(chosen, context_numbers or None)
        if price is None:
            continue

        # Build description by removing the chosen token from the line (rightmost occurrence)
        # and trimming separators/trailing punctuation.
        desc = re.sub(re.escape(chosen) + r'\s*$', '', ln).strip()
        # remove currency symbols that may be in front
        desc = re.sub(r'^[\s\$\€\₹\£]+', '', desc).strip()
        # drop leading item numbering/bullets like "1. Pizza"
        desc = re.sub(r'^\d+[\.\)\-]\s*', '', desc).strip()

        # final safety: price must be positive and not ridiculously huge
        if price <= 0 or price > 1000000:
            continue

        results.append({'description': desc if desc else '(item)', 'price': round(price, 2), 'raw_line': ln})

    return results

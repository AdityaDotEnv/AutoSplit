import re
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

_METADATA_KEYWORDS = [
    "invoice", "invoice no", "invoice#", "bill no", "bill#", "date", "time",
    "gst", "tax", "subtotal", "amount due", "total due", "amount", "phone",
    "tel", "mobile", "order no", "qty", "quantity", "id", "paid", "change",
    "receipt"
]

# Regex to capture a monetary token (currency optional)
_AMT_RE = re.compile(r'(?:(?:₹|\$|€|rs\.?|inr)\s*)?([0-9][0-9\.,]{0,20}[0-9])', re.IGNORECASE)

def _is_metadata_line(line):
    low = (line or "").lower()
    for k in _METADATA_KEYWORDS:
        if k in low:
            return True
    if re.search(r'[/\\\-]{1,}', line) and re.search(r'\d', line):
        return True
    if re.search(r'\d{8,}', line):
        return True
    return False

def _clean_and_convert_token(tok, context_nums=None):
    # reuse logic similar to OCR parser but light-weight
    if tok is None:
        return None
    s = tok.strip()
    s = re.sub(r'[^\d\.,]', '', s)
    if not s:
        return None
    # both separators present?
    if '.' in s and ',' in s:
        if s.rfind('.') > s.rfind(','):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '')
            s = s.replace(',', '.')
    else:
        # only comma: decide decimal vs thousand
        if ',' in s and '.' not in s:
            parts = s.split(',')
            if len(parts[-1]) == 2:
                s = s.replace(',', '.')
            elif len(parts[-1]) == 3:
                s = ''.join(parts)
            else:
                s = s.replace(',', '.')
        # only dot present: if last part >2 digits, remove dots
        elif '.' in s and ',' not in s:
            parts = s.split('.')
            if len(parts[-1]) > 2:
                s = ''.join(parts)

    if '.' in s:
        try:
            return float(s)
        except:
            return None

    # integer token: decide about /100 heuristic
    try:
        val = int(s)
    except:
        return None

    if len(s) >= 5:
        return float(val) / 100.0
    # if context shows decimals present, apply /100 on 4-digit tokens
    if context_nums and any(isinstance(x, float) and not x.is_integer() for x in context_nums):
        if len(s) >= 4:
            return float(val) / 100.0

    return float(val)

def find_total_amount(raw_text):
    """
    Heuristic: scan for lines containing 'total' or similar keywords.
    If not found, scan last numeric-like lines and choose the largest plausible monetary value.
    Returns float or None.
    """
    if not raw_text:
        return None

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    # lowercase version for keyword scanning
    low_lines = [l.lower() for l in lines]

    # gather obvious numeric tokens for context (presence of decimals)
    context_tokens = []
    for ln in lines:
        for m in _AMT_RE.finditer(ln):
            context_tokens.append(m.group(1))
    context_numbers = []
    for tok in context_tokens:
        if '.' in tok:
            try:
                context_numbers.append(float(tok.replace(',', '')))
            except:
                pass

    # 1) Look for explicit total keywords
    total_kw_re = re.compile(r'(total|amount due|amount payable|amount)\s*[:\-]?\s*([0-9][0-9\.,]{0,20}[0-9])', re.IGNORECASE)
    for ln in reversed(lines[-12:]):  # look near the end
        if _is_metadata_line(ln) and ('total' not in ln.lower()):
            # metadata with no total mention -> skip
            continue
        m = total_kw_re.search(ln)
        if m:
            raw_tok = m.group(2)
            total = _clean_and_convert_token(raw_tok, context_numbers)
            if total is not None and total > 0:
                return round(total, 2)

    # 2) If explicit total not found, pick the largest numeric-like value from the last few lines
    candidates = []
    for ln in reversed(lines[-20:]):  # search last 20 lines
        if _is_metadata_line(ln):
            continue
        for m in _AMT_RE.finditer(ln):
            val = _clean_and_convert_token(m.group(1), context_numbers)
            if val is not None and 0 < val < 10000000:
                candidates.append((val, ln))

    if candidates:
        # pick the maximum candidate under the assumption total is usually the highest price
        cand_sorted = sorted(candidates, key=lambda x: x[0], reverse=True)
        # provide a sanity: if the top candidate is more than 20x the second candidate, it might be erroneous
        if len(cand_sorted) >= 2:
            top, second = cand_sorted[0][0], cand_sorted[1][0]
            if second > 0 and top / second > 50:
                # suspicious: fallback to second
                return round(second, 2)
        return round(cand_sorted[0][0], 2)

    return None


def detect_person_item_relations(items, raw_text):
    """
    Given items (list of dicts with keys 'description' and 'raw_line') and the entire raw_text,
    try to match person names to items. Returns dict mapping item_index -> [names]
    """
    if not raw_text or not items:
        return {}

    text = raw_text
    persons = []

    # Use spaCy to extract PERSONs if available
    if nlp:
        try:
            doc = nlp(text)
            persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        except Exception:
            persons = []
    # fallback: simple capitalized word sequences as candidate names
    if not persons:
        # find probable names: sequences of 1-3 capitalized words
        for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', text):
            candidate = m.group(1).strip()
            # small filter: avoid country/city words by length and presence in metadata
            if len(candidate) > 1 and not _is_metadata_line(candidate):
                persons.append(candidate)

    assignments = {}
    lower_text = text.lower()

    for i, it in enumerate(items):
        assigned = []
        raw_line = (it.get('raw_line') or '').lower()
        # Search for person names in the same raw_line (exact word match)
        for name in persons:
            if not name or len(name.strip()) < 2:
                continue
            # match whole words
            if re.search(r'\b' + re.escape(name.lower()) + r'\b', raw_line):
                assigned.append(name)
                continue
            # else check nearby context: find the raw_line in the full text, then check +-80 chars
            idx = lower_text.find(raw_line)
            if idx != -1:
                span = lower_text[max(0, idx - 80): idx + 80 + len(raw_line)]
                if re.search(r'\b' + re.escape(name.lower()) + r'\b', span):
                    assigned.append(name)
        if assigned:
            # dedupe names
            assignments[i] = list(dict.fromkeys(assigned))
    return assignments

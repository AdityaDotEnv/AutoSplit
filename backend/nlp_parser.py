import re
import spacy

try:
    nlp = spacy.load("en_core_web_sm")
except:
    # user must run: python -m spacy download en_core_web_sm
    nlp = None

def find_total_amount(raw_text):
    # heuristic: find "total" lines
    lines = [l.strip() for l in raw_text.lower().splitlines() if l.strip()]
    total_re = re.compile(r'(total|amount due|amount)\s*[:\-]?\s*([0-9]+(?:\.[0-9]{1,2})?)')
    for ln in reversed(lines[-10:]):  # scan last lines
        m = total_re.search(ln)
        if m:
            return float(m.group(2))
    # fallback: last price in text
    price_re = re.compile(r'([0-9]+(?:\.[0-9]{1,2})?)')
    for ln in reversed(lines):
        m = price_re.search(ln)
        if m:
            return float(m.group(1))
    return None

def detect_person_item_relations(items, raw_text):
    # simple heuristic: if lines contain names (capitalized words) near items
    assignments = {}  # item index -> list of names
    if not nlp:
        return assignments
    doc = nlp(raw_text)
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    lower_text = raw_text.lower()
    for i, it in enumerate(items):
        assigned = []
        # check if any person name appears near item's raw line
        for name in persons:
            if name.lower() in it.get('raw_line', '').lower():
                assigned.append(name)
            else:
                # check within +/- 50 chars in raw_text
                idx = lower_text.find(it.get('raw_line', '').lower())
                if idx!=-1:
                    span = lower_text[max(0, idx-50): idx+50+len(it.get('raw_line',''))]
                    if name.lower() in span:
                        assigned.append(name)
        if assigned:
            assignments[i] = assigned
    return assignments

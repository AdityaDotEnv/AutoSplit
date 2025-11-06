from PIL import Image
import pytesseract
import re

# simple wrapper to get text
def image_to_text(image_path):
    img = Image.open(image_path)
    # optional preprocessing could be added
    text = pytesseract.image_to_string(img, lang='eng')
    return text

# extract lines and look for patterns like "item .... 99.00"
PRICE_RE = re.compile(r'([A-Za-z0-9 &\-\(\)\.\/]+?)\s+([0-9]+(?:\.[0-9]{1,2})?)$')

def extract_lines_with_prices(raw_text):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    items = []
    for ln in lines:
        m = PRICE_RE.search(ln)
        if m:
            desc = m.group(1).strip()
            price = float(m.group(2))
            items.append({'description': desc, 'price': price, 'raw_line': ln})
    return items

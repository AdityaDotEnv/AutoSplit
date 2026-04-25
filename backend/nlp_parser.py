import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    import spacy

    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

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
    "amount due",
    "total due",
    "amount",
    "phone",
    "tel",
    "mobile",
    "order no",
    "qty",
    "quantity",
    "id",
    "paid",
    "change",
    "receipt",
]

_AMT_RE = re.compile(
    r"(?:(?:₹|\$|€|rs\.?|inr)\s*)?([0-9][0-9\.,]{0,20}[0-9])", re.IGNORECASE
)


class NullSafeFloat:
    """Type-safe float wrapper with null handling."""

    __slots__ = ("value", "is_null")

    def __init__(self, value: Any = None):
        self.is_null = value is None
        self.value = self._convert(value)

    def _convert(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and (value != value or value == float("inf")):
                return None
            return round(float(value), 2)
        if isinstance(value, str):
            return self._parse_str(value)
        return None

    @staticmethod
    def _parse_str(s: str) -> Optional[float]:
        s = s.strip()
        s = re.sub(r"[^\d\.,]", "", s)
        if not s:
            return None

        has_dot = "." in s
        has_comma = "," in s

        if has_dot and has_comma:
            if s.rfind(".") > s.rfind(","):
                s = s.replace(",", "")
            else:
                s = s.replace(".", "")
                s = s.replace(",", ".")
        elif has_comma and not has_dot:
            parts = s.split(",")
            if len(parts[-1]) == 2:
                s = s.replace(",", ".")
            elif len(parts[-1]) == 3:
                s = "".join(parts)
            else:
                s = s.replace(",", ".")
        elif has_dot and not has_comma:
            parts = s.split(".")
            if len(parts[-1]) > 2:
                s = "".join(parts)

        try:
            return round(float(s), 2)
        except:
            return None

    def get(self) -> Optional[float]:
        return None if self.is_null else self.value

    def __float__(self) -> float:
        return 0.0 if self.is_null else self.value

    def __bool__(self) -> bool:
        return not self.is_null and self.value is not None


@dataclass
class ValidationResult:
    """Result with validation status."""

    is_valid: bool
    value: Any = None
    errors: List[str] = field(default_factory=list)

    @classmethod
    def ok(cls, value: Any) -> "ValidationResult":
        return cls(is_valid=True, value=value, errors=[])

    @classmethod
    def null(cls, error: str) -> "ValidationResult":
        return cls(is_valid=False, value=None, errors=[error])

    @classmethod
    def invalid(cls, error: str) -> "ValidationResult":
        return cls(is_valid=False, value=None, errors=[error])


def _is_metadata_line(line: str) -> bool:
    if not line:
        return False
    low = line.lower()
    for k in _METADATA_KEYWORDS:
        if k in low:
            return True
    if re.search(r"[/\\\-]{1,}", line) and re.search(r"\d", line):
        return True
    if re.search(r"\d{8,}", line):
        return True
    return False


def _sanitize_description(text: str) -> Optional[str]:
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    s = re.sub(r"^[\s\$\€\₹\£]+", "", s)
    s = re.sub(r"^\d+[\.\)\-]\s*", "", s)
    s = s.strip()
    if len(s) < 1:
        return None
    return s if len(s) <= 500 else s[:500]


def find_total_amount(raw_text: str) -> ValidationResult:
    """
    Heuristic: scan for lines containing 'total' or similar keywords.
    Returns ValidationResult with validated total or null error.
    """
    if not raw_text or not raw_text.strip():
        return ValidationResult.null("Empty or None raw_text")

    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    if not lines:
        return ValidationResult.null("No valid lines in text")

    context_tokens = []
    for ln in lines:
        for m in _AMT_RE.finditer(ln):
            context_tokens.append(m.group(1))

    context_numbers = []
    for tok in context_tokens:
        if "." in tok:
            parsed = NullSafeFloat(tok)
            if parsed.value is not None:
                context_numbers.append(parsed.value)

    total_kw_re = re.compile(
        r"(total|amount due|amount payable|amount)\s*[:\-]?\s*([0-9][0-9\.,]{0,20}[0-9])",
        re.IGNORECASE,
    )

    for ln in reversed(lines[-12:]):
        if _is_metadata_line(ln) and "total" not in ln.lower():
            continue
        m = total_kw_re.search(ln)
        if m:
            raw_tok = m.group(2)
            total = NullSafeFloat(raw_tok)
            if total.value is not None and total.value > 0:
                return ValidationResult.ok(total.value)

    candidates = []
    for ln in reversed(lines[-20:]):
        if _is_metadata_line(ln):
            continue
        for m in _AMT_RE.finditer(ln):
            val = NullSafeFloat(m.group(1))
            if val.value is not None and 0 < val.value < 10000000:
                candidates.append((val.value, ln))

    if not candidates:
        return ValidationResult.null("No valid total candidates found")

    cand_sorted = sorted(candidates, key=lambda x: x[0], reverse=True)
    if len(cand_sorted) >= 2:
        top, second = cand_sorted[0][0], cand_sorted[1][0]
        if second > 0 and top / second > 50:
            return ValidationResult.ok(second)

    return ValidationResult.ok(cand_sorted[0][0])


def detect_person_item_relations(
    items: List[dict], raw_text: str
) -> Dict[int, List[str]]:
    """
    Match person names to items. Returns dict mapping item_index -> [names]
    """
    if not raw_text or not items:
        return {}

    text = raw_text
    persons = []

    if nlp:
        try:
            doc = nlp(text)
            persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        except Exception:
            persons = []

    if not persons:
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text):
            candidate = m.group(1).strip()
            if len(candidate) > 1 and not _is_metadata_line(candidate):
                persons.append(candidate)

    assignments = {}
    lower_text = text.lower()

    for i, it in enumerate(items):
        assigned = []
        raw_line = (it.get("raw_line") or "").lower()

        for name in persons:
            if not name or len(name.strip()) < 2:
                continue
            if re.search(r"\b" + re.escape(name.lower()) + r"\b", raw_line):
                assigned.append(name)
                continue
            idx = lower_text.find(raw_line)
            if idx != -1:
                span = lower_text[max(0, idx - 80) : idx + 80 + len(raw_line)]
                if re.search(r"\b" + re.escape(name.lower()) + r"\b", span):
                    assigned.append(name)

        if assigned:
            assignments[i] = list(dict.fromkeys(assigned))

    return assignments

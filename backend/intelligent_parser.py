import os
import re
import time
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, ValidationError
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Global state for 429 cooldown
LAST_429_TIME = 0
COOLDOWN_SECONDS = 60

# --- Gemini-Compatible Fixed Schema Models with Strict Validation ---

class GeminiBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class GeminiItem(GeminiBaseModel):
    id: str = Field(description="Unique identifier for the item")
    name: str = Field(
        description="Clean, recognizable name of the item. Combine multi-line names.",
        min_length=2,
        max_length=100
    )
    quantity: Optional[float] = Field(None, ge=0, description="Quantity purchased")
    unit_price: Optional[float] = Field(None, ge=0, description="Price per unit")
    amount: float = Field(gt=0, description="The total line-level charged amount")
    raw_text: str = Field(description="Original OCR text for this item")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        bad = {"item", "(item)", "unknown", ""}
        if v.strip().lower() in bad:
            raise ValueError("Placeholder name forbidden")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Name must contain letters")
        return v.strip()

    @model_validator(mode="after")
    def validate_math(self):
        if self.quantity and self.unit_price:
            # Allow small rounding tolerance of 0.05
            if abs(self.quantity * self.unit_price - self.amount) > 0.05:
                # We log or warn, but sometimes receipts are just weirdly rounded.
                # Sticking to user requirement: raise error
                raise ValueError("Line math mismatch: quantity * unit_price != amount")
        return self

class DetectedPair(GeminiBaseModel):
    label: str = Field(description="The label or key detected from OCR")
    amount: float = Field(description="The monetary value associated with the label")
    classification: Literal["item", "tax", "service_charge", "discount", "subtotal", "total", "unknown"]

class SharedCharge(GeminiBaseModel):
    label: str = Field(description="Label of the shared charge (e.g. Service Charge, Tip)")
    amount: float = Field(description="Amount of the shared charge")

class TaxEntry(GeminiBaseModel):
    label: str = Field(description="Tax label (e.g. GST, CGST)")
    rate: Optional[float] = Field(None, ge=0, description="Tax rate percentage if shown")
    amount: float = Field(description="Tax amount")

class FixedTotals(GeminiBaseModel):
    subtotal: Optional[float] = None
    grand_total: Optional[float] = None
    amount_paid: Optional[float] = None
    balance_due: Optional[float] = None

class UnknownPair(GeminiBaseModel):
    label: str
    amount: float

class ReconciliationInfo(GeminiBaseModel):
    calculated_total: float
    stated_total: float
    difference: float
    reconciled: bool

class GeminiReceiptData(GeminiBaseModel):
    merchant: Optional[str] = None
    currency: Optional[str] = None
    items: List[GeminiItem] = Field(default_factory=list)
    detected_pairs: List[DetectedPair] = Field(default_factory=list)
    shared_charges: List[SharedCharge] = Field(default_factory=list)
    taxes: List[TaxEntry] = Field(default_factory=list)
    totals: FixedTotals = Field(default_factory=FixedTotals)
    unknown_pairs: List[UnknownPair] = Field(default_factory=list)
    reconciliation: ReconciliationInfo

def refine_with_gemini(raw_text: str) -> Optional[GeminiReceiptData]:
    """
    Uses Gemini with a fixed, strict schema. Handles 429 cooldowns and validation guards.
    """
    global LAST_429_TIME
    
    # Check cooldown
    if time.time() - LAST_429_TIME < COOLDOWN_SECONDS:
        print(f"Gemini on cooldown ({int(COOLDOWN_SECONDS - (time.time() - LAST_429_TIME))}s remaining)")
        return None

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not found. Skipping intelligent parsing.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        
        system_prompt = """You are a structured receipt extraction engine.
Extract all OCR text from the bill image and return structured expense data.

IMPORTANT:
Do NOT return dynamic key-value dictionaries. ALWAYS return arrays of objects.
Avoid additionalProperties or arbitrary maps. Use the fixed schema provided.

ITEM EXTRACTION (CRITICAL)
Every item MUST have a non-empty human-readable name.
NEVER return: "name":"item", "name":"(item)", or "name":"unknown".
Use the actual product description from the receipt.

VERTICAL MERGE RULES:
If a line has text but no amount, and the next line has text + quantity + amount, merge them.
Pattern:
Line1: words only (e.g. "SHAKARKAND")
Line2: words + qty + amount (e.g. "CHAAT 1 300")
Result: Combine Line1 + Line2 item text (e.g. "Shakarkand Chaat").

Wrapped names must be merged. If an amount exists, there must be a valid item name.
Do not promote Sub Total, GST, CGST, SGST, Total Qty, or Round Off into items. Those belong in taxes/shared_charges/totals only.

DETECTION:
- Capture every detected monetary label-value pair in 'detected_pairs'.
- Normalize all amounts as decimal numbers (no currency symbols).

RECONCILIATION:
- Verify: sum(items) + charges + taxes - discounts matches grand_total.
- Return ONLY JSON conforming exactly to the provided schema. No prose. No markdown."""
        
        user_prompt = f"Extract structured receipt data from this OCR:\n\n{raw_text}"
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type='application/json',
                response_schema=GeminiReceiptData,
                temperature=0.1
            ),
        )
        
        if not response.parsed:
            print("Gemini returned empty/malformed parsed object.")
            return None
            
        return response.parsed

    except ValidationError as ve:
        print(f"Gemini schema validation failed: {ve}")
        return None
    except Exception as e:
        error_msg = str(e)
        if "RESOURCE_EXHAUSTED" in error_msg:
            print("Gemini API quota exhausted (429). Starting cooldown.")
            LAST_429_TIME = time.time()
        else:
            print(f"Intelligent parsing error: {error_msg}")
        return None

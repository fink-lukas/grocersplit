import time
import json
import re
import threading
import asyncio
import base64
import io
from typing import Optional, List, Dict, Any, Tuple
import httpx
from PIL import Image
from app.core.config import settings

# Try importing the modern unified google.genai SDK; fall back if not yet available in environment
try:
    from google import genai
    from google.genai import types
    HAS_NEW_GENAI = True
except ImportError:
    import google.generativeai as legacy_genai
    HAS_NEW_GENAI = False

# Setup API Key Cycling
API_KEYS = settings.gemini_api_keys
if not API_KEYS:
    print("WARNING: No GEMINI_API_KEY found in environment variables.")

current_key_idx = 0
key_lock = threading.Lock()

def get_current_key():
    with key_lock:
        return API_KEYS[current_key_idx] if API_KEYS else None

def cycle_api_key():
    global current_key_idx
    with key_lock:
        if len(API_KEYS) > 1:
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            new_key = API_KEYS[current_key_idx]
            if not HAS_NEW_GENAI:
                legacy_genai.configure(api_key=new_key)
            print(f"Switched to API Key {current_key_idx + 1}/{len(API_KEYS)}")
            return True
        return False

if not HAS_NEW_GENAI and get_current_key():
    legacy_genai.configure(api_key=get_current_key())

class RateLimitExceeded(Exception):
    pass

class ParsingFailed(Exception):
    pass


PROMPT_V3 = """You are an expert OCR and financial data extraction engine specializing in European retail receipts (e.g. Austria, Germany, Switzerland).

Your goal is 100% accurate, line-by-line itemization and mathematical reconciliation with the printed grand total.

Extraction Guidelines:

1. Horizontal Baseline & Column Alignment:
   - Each item row has its description on the left and its final price / tax bracket on the far right.
   - Track horizontally across the line: match each price strictly to the text sitting on that exact same horizontal baseline.
   - European decimal commas must be converted to standard floats (e.g., "1,39" -> 1.39, "71,57" -> 71.57).

2. Cancellations & Voided Items (Storno / Sofortstorno):
   - When a cashier accidentally rings an item twice or makes a mistake, a cancellation line appears on the receipt:
     Example:
       107044 Laugenbaguette         1,39 A
       107044 Laugenbaguette         1,39 A
       Sofortstorno
       - 107044 Laugenbaguette      -1,39 A
   - The 'Sofortstorno' cancels out one of the preceding items. The customer did NOT buy that cancelled item.
   - You MUST net out Stornos with their corresponding item!
     In the example above, return EXACTLY ONE 'Laugenbaguette' with quantity: 1, total_price: 1.39.
     Set `storno_reconciled: "2 scanned minus 1 Sofortstorno = 1 purchased"`.
   - Do NOT output phantom cancelled items or negative storno lines as separate purchased goods.

3. Bottle Deposits (Pfand / Einweg / Mehrweg / Leergut):
   - Standard Austrian/German single-use container deposit (Einwegpfand) is €0.25 per unit (can or bottle).
   - If a receipt prints deposit for multiple containers (e.g. 'Einweg Pfand 1,00' or '4 x 0,25' following 4 cans of Red Bull):
     The total price charged on that line is €1.00!
     Record: `quantity: 4`, `unit_price: 0.25`, `total_price: 1.00` (since 4 * 0.25 = 1.00).
     NEVER calculate 4 x 1.00 = 4.00! The `total_price` must strictly equal the printed line amount (€1.00).
   - If Pfand is listed as a single line (e.g. 'Pfand 0,25'): `quantity: 1`, `unit_price: 0.25`, `total_price: 0.25`.
   - Returned bottles / crates (e.g. 'Leergut -2,50' or 'Pfandbon'):
     Set `item_type: "deposit"`, `total_price: -2.50` (negative).

4. Discounts (Item-Level vs Cart-Level):
   - Item-Level Discounts (e.g. '-25% Pickerl -0,50', 'Aktion -0,70' directly under a product):
     Apply directly to that product!
     Record: `original_price: 2.99`, `discount_amount: 0.50`, `total_price: 2.49` (the net payable price).
     This ensures whoever claims the item automatically pays the net discounted price.
   - Cart-Level Discounts / Vouchers (e.g. 'Gutschein -10,00' or 'Treuebonus' at the bottom):
     Set `item_type: "cart_discount"`, `total_price: -10.00`.

5. Weighted Produce (Meat, Deli, Vegetables, Fruit):
   - Austrian/German receipts format weighted goods with the final charged price in the right column, and weight calculation on a sub-line:
     Example:
       559117 Gustospieße                         6,95 A
           0,480 kg x   14,48 EUR/kg
     Here:
       - The right column '6,95' is the FINAL line total charged to the customer (`total_price: 6.95`).
       - The subline '0,480 kg x 14,48 EUR/kg' specifies the weight and kg rate (`quantity: 0.480`, `unit: "kg"`, `unit_price: 14.48`).
       - Verification: 0.480 * 14.48 = 6.9504 -> 6.95 EUR.
       - NEVER use the final line total (6.95) as the kg rate! The number followed by EUR/kg (14.48) is the unit rate.

6. Strict Mathematical Reconciliation & Grand Total Identification:
   - Sum every item's `total_price` (including deposits and cart discounts).
   - Locate the printed `grand_total`: on European receipts, this is the overall final payable amount printed at the bottom of the itemized list, labeled with terms like 'SUMME', 'GESAMTBETRAG', 'HOFER PREIS', 'TOTAL', 'BAR', or 'ZU ZAHLEN' (e.g. 'HOFER PREIS 71,57' or 'SUMME 90,55').
   - NEVER confuse the last item's price, bottle deposit, or subtotal with the receipt grand total! The grand total encompasses the entire purchase.
   - Set `financials.grand_total` and `reconciliation.printed_total` to this printed grand total.
   - Compute `difference = round(printed_total - calculated_items_sum, 2)`.
   - Set `is_match: true` if abs(difference) < 0.02.
   - Verify `actual_items_count` matches the physical items purchased (e.g. 26 Artikel).
"""

SCHEMA_V3 = {
    "type": "object",
    "properties": {
        "merchant": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "branch": {"type": "string"},
                "address": {"type": "string"}
            },
            "required": ["name"]
        },
        "metadata": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM:SS"},
                "payment_method": {"type": "string"},
                "card_last_four": {"type": "string"},
                "printed_item_count": {"type": "integer"},
                "actual_items_count": {"type": "integer"}
            },
            "required": ["date"]
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "description": {"type": "string"},
                    "item_type": {
                        "type": "string",
                        "enum": ["product", "deposit", "cart_discount"]
                    },
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "unit_price": {"type": "number"},
                    "original_price": {"type": "number"},
                    "discount_amount": {"type": "number"},
                    "total_price": {"type": "number"},
                    "linked_beverage": {"type": "string"},
                    "storno_reconciled": {"type": "string"}
                },
                "required": ["description", "item_type", "quantity", "total_price"]
            }
        },
        "financials": {
            "type": "object",
            "properties": {
                "grand_total": {
                    "type": "number",
                    "description": "The printed grand total for the whole receipt (e.g. SUMME, GESAMTBETRAG, HOFER PREIS). NEVER an individual line item."
                },
                "currency": {"type": "string"}
            },
            "required": ["grand_total", "currency"]
        },
        "reconciliation": {
            "type": "object",
            "properties": {
                "calculated_items_sum": {"type": "number"},
                "printed_total": {
                    "type": "number",
                    "description": "The final overall grand total printed on the receipt."
                },
                "difference": {"type": "number"},
                "is_match": {"type": "boolean"},
                "storno_notes": {"type": "string"},
                "discrepancy_explanation": {"type": "string"}
            },
            "required": ["calculated_items_sum", "printed_total", "difference", "is_match"]
        }
    },
    "required": ["merchant", "metadata", "items", "financials", "reconciliation"]
}

def pil_image_to_base64(img: Image.Image, max_dim: int = 2400) -> str:
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buffered, format="JPEG", quality=90)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

async def call_new_api(messages: list, response_format: dict = None) -> str:
    if not settings.NEW_API_BASE_URL or not settings.NEW_API_KEY:
        raise ParsingFailed("New-API configuration is missing NEW_API_BASE_URL or NEW_API_KEY.")

    headers = {
        "Authorization": f"Bearer {settings.NEW_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.NEW_API_MODEL,
        "messages": messages,
        "temperature": 0.0,
    }
    if response_format:
        payload["response_format"] = response_format

    url = f"{settings.NEW_API_BASE_URL.rstrip('/')}/chat/completions"
    max_retries = 3
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                res_data = response.json()
                return res_data["choices"][0]["message"]["content"]
            elif response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            else:
                raise ParsingFailed(f"New-API failed with status {response.status_code}: {response.text}")
        except httpx.RequestError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise ParsingFailed(f"Failed to connect to New-API: {e}")

    raise RateLimitExceeded("New-API rate limits or connection failures exceeded after all retries.")

def _get_json_from_response(content: str) -> Optional[dict]:
    try:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        return json.loads(content)
    except Exception as e:
        print(f"Error parsing response JSON: {e}")
        return None

async def parse_receipt(file_path: str):
    """
    Parses receipt using single-shot multimodal Gemini 2.5 Flash.
    Converts extracted values to CENTS for GrocerSplit.
    """
    img = Image.open(file_path)
    use_new_api = bool(settings.NEW_API_BASE_URL and settings.NEW_API_KEY)

    data = None
    if use_new_api:
        base64_img = pil_image_to_base64(img)
        full_system_prompt = f"{PROMPT_V3}\n\nStrictly output ONLY valid JSON matching this schema:\n{json.dumps(SCHEMA_V3, indent=2)}"
        messages = [
            {"role": "system", "content": full_system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all items, totals, and metadata from this receipt according to the guidelines."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }
        ]
        raw_resp = await call_new_api(messages, response_format={"type": "json_object"})
        data = _get_json_from_response(raw_resp)
    else:
        if not get_current_key():
            raise ParsingFailed("No GEMINI_API_KEY configured.")

        # Run direct Google GenAI SDK call
        max_retries = 4
        base_delay = 2.0

        for attempt in range(max_retries):
            try:
                if HAS_NEW_GENAI:
                    client = genai.Client(api_key=get_current_key())
                    config = types.GenerateContentConfig(
                        temperature=0.0,
                        thinking_config=types.ThinkingConfig(),
                        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
                        response_mime_type="application/json",
                        response_schema=SCHEMA_V3,
                        system_instruction=PROMPT_V3,
                    )
                    user_content = [
                        "Extract all items, totals, and metadata from this receipt according to the guidelines.",
                        img
                    ]
                    # Run in threadpool to avoid blocking event loop
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model='gemini-2.5-flash',
                        contents=user_content,
                        config=config
                    )
                    data = _get_json_from_response(response.text or "")
                    break
                else:
                    # Legacy SDK fallback
                    model = legacy_genai.GenerativeModel(
                        'gemini-2.5-flash',
                        generation_config={"response_mime_type": "application/json"}
                    )
                    user_content = [
                        f"{PROMPT_V3}\n\nStrictly output JSON according to schema:\n{json.dumps(SCHEMA_V3)}",
                        img
                    ]
                    response = await asyncio.to_thread(model.generate_content, user_content)
                    data = _get_json_from_response(response.text or "")
                    break

            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(x in err_str for x in ["429", "500", "502", "503", "504", "unavailable", "quota", "high demand"])
                if is_transient and attempt < max_retries - 1:
                    if "quota" in err_str or "429" in err_str:
                        if cycle_api_key():
                            await asyncio.sleep(1)
                            continue
                    delay = base_delay * (2 ** attempt)
                    print(f"Gemini API transient error ({type(e).__name__}). Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                raise ParsingFailed(f"Gemini API extraction failed: {e}")

    if not data or not isinstance(data.get("items"), list):
        raise ParsingFailed("Invalid JSON format returned from Gemini API.")

    parsed_items = data.get("items", [])
    financials = data.get("financials", {})
    reconciliation = data.get("reconciliation", {})

    grand_total_float = float(financials.get("grand_total") or 0.0)
    if grand_total_float == 0.0 and reconciliation.get("printed_total") is not None:
        grand_total_float = float(reconciliation.get("printed_total") or 0.0)

    receipt_total_cents = int(round(grand_total_float * 100))

    # Convert items to GrocerSplit format with cent amounts and rich metadata
    grocer_items = []
    for it in parsed_items:
        tp_float = float(it.get("total_price", 0.0))
        item_line_total_cents = int(round(tp_float * 100))

        orig_price_float = it.get("original_price")
        orig_cents = int(round(orig_price_float * 100)) if orig_price_float is not None else None

        disc_float = float(it.get("discount_amount", 0.0) or 0.0)
        disc_cents = int(round(disc_float * 100))

        qty = float(it.get("quantity", 1.0))
        unit = it.get("unit")
        unit_price_float = it.get("unit_price")

        # Determine price in cents:
        # In GrocerSplit, item.price represents unit price, and line total = round(price * quantity).
        if qty <= 0:
            qty = 1.0
            price_cents = item_line_total_cents
        elif abs(qty - 1.0) < 0.0001:
            price_cents = item_line_total_cents
        elif unit_price_float is not None and abs(round(round(unit_price_float * 100) * qty) - item_line_total_cents) <= 2:
            # Validated unit price matches total (e.g. 14.48 EUR/kg * 0.480 kg = 6.95 EUR)
            price_cents = int(round(unit_price_float * 100))
        else:
            # Calculate unit price from total to ensure exact line total multiplication
            price_cents = int(round(item_line_total_cents / qty))

        # Build notes if weighted
        notes = it.get("linked_beverage") or it.get("storno_reconciled")
        if unit in ["kg", "g", "l", "ml"] and unit_price_float is not None:
            weight_note = f"{qty} {unit} @ €{unit_price_float:.2f}/{unit}"
            notes = f"{notes} ({weight_note})" if notes else weight_note

        grocer_items.append({
            "name": it.get("description", "Item").strip(),
            "raw_name": it.get("description", "Item").strip(),
            "sku": it.get("sku"),
            "item_type": it.get("item_type", "product"),
            "price": price_cents,
            "original_price": orig_cents,
            "discount_amount": disc_cents,
            "quantity": qty,
            "unit": unit,
            "notes": notes
        })

    items_sum_cents = sum(int(round(it["price"] * it["quantity"])) for it in grocer_items)
    mismatch = abs(items_sum_cents - receipt_total_cents) > 2  # Tolerance of 2 cents

    return {
        "items": grocer_items,
        "total": receipt_total_cents,
        "mismatch": mismatch,
        "items_sum": items_sum_cents,
        "merchant": data.get("merchant", {}),
        "metadata": data.get("metadata", {}),
        "reconciliation": reconciliation
    }

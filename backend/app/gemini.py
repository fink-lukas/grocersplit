import os
import google.generativeai as genai
from PIL import Image
import json
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT_ITEMS = """
You are a receipt scanning expert. Analyze this receipt (image or PDF) and extract the items bought.
Return the result ONLY as a JSON object with the following structure:
{
  "items": [
    {
      "name": "Clean name of the item",
      "price": 123, (unit price in cents, integer)
      "quantity": 1 (integer)
    }
  ]
}

Important:
1. All prices must be in CENTS (e.g., 2.99 -> 299).
2. If multiple quantities of the same item are on one line, extract the unit price and the quantity.
3. Ignore items that are not products (like discounts, tax summaries, or meta info if possible, but keep specific discounts if they apply to an item).
4. Be as accurate as possible with the item names.
"""

PROMPT_TOTAL = """
Analyze this receipt and extract ONLY the total amount.
Return the result ONLY as a JSON object with the following structure:
{
  "total": 1234 (total amount of the receipt in cents, integer)
}
"""

def _get_json_from_response(response):
    try:
        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        return json.loads(content)
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Raw response: {response.text}")
        return None

def parse_receipt(file_path: str):
    img = Image.open(file_path)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Run both requests
    items_response = model.generate_content([PROMPT_ITEMS, img])
    total_response = model.generate_content([PROMPT_TOTAL, img])
    
    items_data = _get_json_from_response(items_response)
    total_data = _get_json_from_response(total_response)
    
    if not items_data or not total_data:
        return None
        
    items = items_data.get("items", [])
    total = total_data.get("total", 0)
    
    # Integrity check
    items_sum = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
    mismatch = items_sum != total
    
    return {
        "items": items,
        "total": total,
        "mismatch": mismatch,
        "items_sum": items_sum
    }

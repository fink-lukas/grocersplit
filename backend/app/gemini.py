import os
import google.generativeai as genai
from PIL import Image
import json
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT = """
You are a receipt scanning expert. Analyze this receipt (image or PDF) and extract the items bought.
Return the result ONLY as a JSON object with the following structure:
{
  "items": [
    {
      "name": "Clean name of the item",
      "price": 123, (unit price in cents, integer)
      "quantity": 1 (integer)
    }
  ],
  "total": 1234 (total amount of the receipt in cents, integer)
}

Important:
1. All prices must be in CENTS (e.g., 2.99 -> 299).
2. If multiple quantities of the same item are on one line, extract the unit price and the quantity.
3. Ignore items that are not products (like discounts, tax summaries, or meta info if possible, but keep specific discounts if they apply to an item).
4. Be as accurate as possible with the item names.
"""

def parse_receipt(file_path: str):
    # Determine if it's an image or PDF
    # For now, let's assume image
    img = Image.open(file_path)
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content([PROMPT, img])
    
    # Extract JSON from response
    try:
        # Gemini sometimes wraps JSON in markdown blocks
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

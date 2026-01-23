import os
import google.generativeai as genai
from PIL import Image
import json
import difflib
import re
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT_OCR = """
Transcribe all the text from this receipt exactly as it appears, line by line. 
Do not try to interpret or format the data yet. Just give me the raw text content.
"""

PROMPT_TEXT_TO_JSON = """
You are a data extraction expert. I will give you the raw text transcribed from a receipt.
Your job is to extract the items purchased and the total amount.

Return the result ONLY as a JSON object with this structure:
{
  "items": [
    {
      "name": "Clean name of the item",
      "price": 123, (unit price in cents, integer)
      "quantity": 1 (integer)
    }
  ],
  "total": 1234 (total amount in cents, integer)
}

Important:
1. Prices must be in CENTS (2.99 -> 299).
2. If the text has unit price and quantity (e.g. "2 x 1.50"), capture that.
3. Ignore tax, subtotals, card info, etc. unless it's the final Total.
4. Calculate the sum of items yourself to check against the total if possible, but prioritize what is written.
5. If a line contains only a price (e.g. "0,25") appearing immediately after an item, treat it as a related item (e.g. "Pfand" or "Deposit").
6. If an item is listed but has no price visible, include it with price 0.
7. CRITICAL: Do NOT group identical items. If "Apple" appears 3 times on 3 lines, return 3 separate item objects. This is required for splitting costs.

Raw Text:
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
        # print(f"Raw response: {response.text}")
        return None

def normalize_line(line):
    """
    Normalizes a line for fuzzy matching.
    Aggressive character replacement to handle common OCR errors (0/O, 1/l/I, etc.)
    and stripping non-alphanumeric characters.
    """
    s = line.lower()
    s = s.replace('o', '0').replace('l', '1').replace('i', '1').replace('z', '2').replace('s', '5').replace('b', '8')
    return re.sub(r'[^a-z0-9]', '', s)

def stitch_text_parts(parts):
    """
    Stitches overlapping text parts into a single continuous text.
    Uses fuzzy matching to identify and merge overlaps.
    """
    if not parts:
        return ""
    
    full_lines = parts[0].splitlines()
    
    for i in range(1, len(parts)):
        prev_lines = full_lines
        next_lines = parts[i].splitlines()
        
        # Optimize: Only look at the "overlap region" candidates.
        # Overlap is typically ~20% of the slice (300px/1500px).
        # We check the last 50 lines of prev and first 50 of next.
        SEARCH_WINDOW = 50
        
        prev_window_start = max(0, len(prev_lines) - SEARCH_WINDOW)
        prev_candidate = prev_lines[prev_window_start:]
        
        next_candidate = next_lines[:SEARCH_WINDOW]
        
        prev_norm = [normalize_line(line) for line in prev_candidate]
        next_norm = [normalize_line(line) for line in next_candidate]
        
        matcher = difflib.SequenceMatcher(None, prev_norm, next_norm)
        # Find the longest match in the candidate windows
        match = matcher.find_longest_match(0, len(prev_norm), 0, len(next_norm))
        
        # We require a match of at least 2 lines to consider it a valid overlap
        if match.size >= 2: 
            # Calculate indices relative to the full lists
            cut_index_in_prev = prev_window_start + match.a
            start_index_in_next = match.b
            
            # Stitch: Take prev up to the match, and append next starting from the match
            full_lines = prev_lines[:cut_index_in_prev] + next_lines[start_index_in_next:]
        else:
            # Fallback: Just append if no strong overlap found
            full_lines.extend(next_lines)
            
    return "\n".join(full_lines)


def slice_image(img, max_height=1000, overlap=200):
    """
    Slices a tall image into overlapping chunks.
    """
    width, height = img.size
    slices = []
    
    if height <= max_height:
        return [img]
    
    current_y = 0
    while current_y < height:
        target_y = min(current_y + max_height, height)
        # Crop box: (left, upper, right, lower)
        box = (0, current_y, width, target_y)
        slices.append(img.crop(box))
        
        if target_y == height:
            break
            
        current_y += (max_height - overlap)
        
    return slices

def parse_receipt(file_path: str):
    img = Image.open(file_path)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Check if image needs slicing
    # Assuming standard width (e.g. 500-1000px), if height > 1500px it's "long"
    slices = slice_image(img, max_height=1500, overlap=300)
    
    raw_text_parts = []
    
    # Step 1: Transcribe each slice
    for i, slice_img in enumerate(slices):
        try:
            # print(f"Transcribing slice {i+1}/{len(slices)}")
            ocr_response = model.generate_content([PROMPT_OCR, slice_img])
            raw_text_parts.append(ocr_response.text)
        except Exception as e:
            print(f"OCR Step Failed for slice {i}: {e}")
            # Continue with other slices if one fails, though it's bad.
    
    # Stitch the parts together handling overlaps
    full_text = stitch_text_parts(raw_text_parts)
    
    # Step 2: Parse Raw Text to JSON
    try:
        parse_response = model.generate_content(PROMPT_TEXT_TO_JSON + full_text)
        data = _get_json_from_response(parse_response)
    except Exception as e:
        print(f"Parsing Step Failed: {e}")
        return None
    
    if not data:
        return None
        
    items = data.get("items", [])
    total = data.get("total", 0)
    
    # Integrity check
    items_sum = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
    mismatch = items_sum != total
    
    return {
        "items": items,
        "total": total,
        "mismatch": mismatch,
        "items_sum": items_sum
    }

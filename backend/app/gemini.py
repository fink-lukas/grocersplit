import os
import time
import google.generativeai as genai
from PIL import Image
import json
import difflib
import re
import threading
from dotenv import load_dotenv

load_dotenv()

# Setup API Key Cycling
raw_keys = os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]
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
            genai.configure(api_key=new_key)
            print(f"Switched to API Key {current_key_idx + 1}/{len(API_KEYS)}")
            return True
        return False

if get_current_key():
    genai.configure(api_key=get_current_key())

# Throttler
last_request_time = 0
throttle_lock = threading.Lock()
THROTTLE_DELAY = 7.0  # 7 seconds

def wait_for_throttle():
    global last_request_time
    with throttle_lock:
        now = time.time()
        elapsed = now - last_request_time
        if elapsed < THROTTLE_DELAY:
            time.sleep(THROTTLE_DELAY - elapsed)
        last_request_time = time.time()

class RateLimitExceeded(Exception):
    pass

class ParsingFailed(Exception):
    pass

def generate_with_retry(model, *args, **kwargs):
    """
    Executes model.generate_content with exponential backoff, rate limiting, and API key cycling.
    """
    max_retries = 3
    base_delay = 2.0
    
    for attempt in range(max_retries):
        wait_for_throttle()
        try:
            response = model.generate_content(*args, **kwargs)
            return response
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "resource exhausted" in error_msg or "quota" in error_msg:
                print(f"Rate limit hit (Attempt {attempt + 1}/{max_retries}): {e}")
                if cycle_api_key():
                    # If we successfully cycled, try again immediately with new key
                    continue
                else:
                    # No other keys, do exponential backoff
                    delay = base_delay * (2 ** attempt)
                    print(f"Sleeping for {delay}s...")
                    time.sleep(delay)
            else:
                # Other errors (e.g., 500), just raise
                raise e
                
    raise RateLimitExceeded("Google Gemini API rate limits exceeded after all retries. Please wait a minute and try again.")


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
      "price": 123,
      "quantity": 1
    }
  ],
  "total": 1234
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
        return None

def normalize_line(line):
    s = line.lower()
    s = s.replace('o', '0').replace('l', '1').replace('i', '1').replace('z', '2').replace('s', '5').replace('b', '8')
    return re.sub(r'[^a-z0-9]', '', s)

def stitch_text_parts(parts):
    if not parts:
        return ""
    full_lines = parts[0].splitlines()
    for i in range(1, len(parts)):
        prev_lines = full_lines
        next_lines = parts[i].splitlines()
        SEARCH_WINDOW = 50
        prev_window_start = max(0, len(prev_lines) - SEARCH_WINDOW)
        prev_candidate = prev_lines[prev_window_start:]
        next_candidate = next_lines[:SEARCH_WINDOW]
        prev_norm = [normalize_line(line) for line in prev_candidate]
        next_norm = [normalize_line(line) for line in next_candidate]
        matcher = difflib.SequenceMatcher(None, prev_norm, next_norm)
        match = matcher.find_longest_match(0, len(prev_norm), 0, len(next_norm))
        if match.size >= 2: 
            cut_index_in_prev = prev_window_start + match.a
            start_index_in_next = match.b
            full_lines = prev_lines[:cut_index_in_prev] + next_lines[start_index_in_next:]
        else:
            full_lines.extend(next_lines)
    return "\n".join(full_lines)

def slice_image(img, max_height=1000, overlap=200):
    width, height = img.size
    slices = []
    if height <= max_height:
        return [img]
    current_y = 0
    while current_y < height:
        target_y = min(current_y + max_height, height)
        box = (0, current_y, width, target_y)
        slices.append(img.crop(box))
        if target_y == height:
            break
        current_y += (max_height - overlap)
    return slices

def parse_receipt(file_path: str):
    img = Image.open(file_path)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    slices = slice_image(img, max_height=1500, overlap=300)
    raw_text_parts = []
    
    for i, slice_img in enumerate(slices):
        try:
            ocr_response = generate_with_retry(model, [PROMPT_OCR, slice_img])
            raw_text_parts.append(ocr_response.text)
        except Exception as e:
            print(f"OCR Step Failed for slice {i}: {e}")
            if isinstance(e, RateLimitExceeded):
                raise e
    
    if not len(raw_text_parts):
         raise ParsingFailed("Failed to transcribe any text from the image.")

    full_text = stitch_text_parts(raw_text_parts)
    
    json_model = genai.GenerativeModel(
        'gemini-2.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
    
    try:
        parse_response = generate_with_retry(json_model, PROMPT_TEXT_TO_JSON + full_text)
        data = _get_json_from_response(parse_response)
    except Exception as e:
        print(f"Parsing Step Failed: {e}")
        if isinstance(e, RateLimitExceeded):
            raise e
        raise ParsingFailed("Failed to extract JSON from text.") from e
    
    if not data or not isinstance(data.get("items"), list):
        raise ParsingFailed("Invalid JSON format returned from Gemini.")
        
    items = data.get("items", [])
    total = data.get("total", 0)
    
    if not items and total == 0:
        raise ParsingFailed("Gemini returned empty items list and 0 total.")

    items_sum = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
    mismatch = items_sum != total
    
    return {
        "items": items,
        "total": total,
        "mismatch": mismatch,
        "items_sum": items_sum
    }

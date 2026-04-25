import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ocr_parser import image_to_text, extract_lines_with_prices

if __name__ == "__main__":
    image_path = "uploads/1762391984.456254_WhatsApp Image 2025-11-06 at 11.39.57_dc34555c.jpg"
    print(f"Testing OCR on {image_path}")
    result = image_to_text(image_path)
    print(f"Result Valid: {result.is_valid}")
    if result.error:
        print(f"Error: {result.error}")
    print("--- OCR TEXT ---")
    print(result.text)
    
    print("--- EXTRACTED LINES ---")
    items = extract_lines_with_prices(result.text)
    for item in items:
        print(item)

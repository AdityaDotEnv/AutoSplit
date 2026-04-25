import os
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

ocr_engine = RapidOCR()

def extract_ocr_tokens(image_path):
    if not os.path.exists(image_path):
        return []
    
    result, _ = ocr_engine(image_path)
    tokens = []
    if not result:
        return tokens
    
    for box, text, score in result:
        # box is [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        box_np = np.array(box)
        x1 = float(np.min(box_np[:, 0]))
        y1 = float(np.min(box_np[:, 1]))
        x2 = float(np.max(box_np[:, 0]))
        y2 = float(np.max(box_np[:, 1]))
        
        tokens.append({
            "text": text,
            "bbox": [x1, y1, x2, y2]
        })
    return tokens

def group_tokens_into_lines(tokens, y_tolerance=15):
    """
    Groups tokens into lines using y-coordinate clustering.
    Returns list of dicts with: text, left_x, right_x, y, tokens
    """
    if not tokens:
        return []
    
    # Sort tokens by vertical center y-coordinate
    sorted_tokens = sorted(tokens, key=lambda t: (t['bbox'][1] + t['bbox'][3]) / 2)
    
    lines = []
    current_line = [sorted_tokens[0]]
    current_y = (sorted_tokens[0]['bbox'][1] + sorted_tokens[0]['bbox'][3]) / 2
    
    for token in sorted_tokens[1:]:
        token_y = (token['bbox'][1] + token['bbox'][3]) / 2
        if abs(token_y - current_y) <= y_tolerance:
            current_line.append(token)
            current_y = sum((t['bbox'][1] + t['bbox'][3]) / 2 for t in current_line) / len(current_line)
        else:
            lines.append(current_line)
            current_line = [token]
            current_y = token_y
            
    if current_line:
        lines.append(current_line)
        
    grouped_lines = []
    for line_tokens in lines:
        # Sort tokens in the line by x-coordinate (left to right)
        line_tokens = sorted(line_tokens, key=lambda t: t['bbox'][0])
        
        text = " ".join(t['text'] for t in line_tokens)
        left_x = line_tokens[0]['bbox'][0]
        right_x = max(t['bbox'][2] for t in line_tokens)
        y = sum((t['bbox'][1] + t['bbox'][3]) / 2 for t in line_tokens) / len(line_tokens)
        
        grouped_lines.append({
            "text": text,
            "left_x": left_x,
            "right_x": right_x,
            "y": y,
            "tokens": line_tokens
        })
        
    return grouped_lines

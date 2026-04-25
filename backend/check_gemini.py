import os
from dotenv import load_dotenv
from intelligent_parser import refine_with_gemini

load_dotenv()
res = refine_with_gemini("BURGER 25.0\nCOKE 5.0\nTOTAL 30.0")
print(f"Result: {res}")
if res:
    for it in res.items:
        print(f"- {it.description}: {it.price}")
else:
    print("Gemini failed or skipped.")

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    print("No GOOGLE_API_KEY found.")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("Available models:")
        for model in client.models.list():
            print(f"- {model.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

"""TRACEBACK Gemini AI client."""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured.")


client = genai.Client(api_key=API_KEY)


def ask_gemini(prompt: str) -> str:
    """Send a prompt to Gemini and return the text response."""
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    return response.text

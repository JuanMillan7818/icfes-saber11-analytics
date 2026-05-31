from __future__ import annotations

import os

GEMINI_MODEL = "gemini-2.0-flash"


def get_gemini_key() -> str | None:
    try:
        import streamlit as st  # type: ignore

        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            key = st.secrets["GEMINI_API_KEY"]
            if key and key.strip():
                return key.strip()
    except Exception:
        pass
    key = os.getenv("GEMINI_API_KEY", "")
    return key.strip() if key.strip() else None


def get_gemini_client():
    from google import genai  # type: ignore

    key = get_gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada.")
    return genai.Client(api_key=key)


def generate(prompt: str) -> str:
    client = get_gemini_client()
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text

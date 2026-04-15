"""Text processing for Plus / Rage / Emoji modes.

Provider is detected from the API key prefix (same logic as transcriber.py):
  sk-...   → OpenAI  (model: gpt-4o-mini)
  gsk_...  → Groq    (model: llama-3.1-8b-instant)
"""
from __future__ import annotations


def process(text: str, mode: str, api_key: str,
            prompt_template: str, emoji_density: int = 5) -> str:
    """Transform *text* for the given mode. Normal mode is a no-op."""
    if mode == "normal":
        return text

    system_prompt = prompt_template
    if "{density}" in system_prompt:
        system_prompt = system_prompt.replace("{density}", str(emoji_density))

    if api_key.startswith("gsk_"):
        return _groq(text, system_prompt, api_key)
    return _openai(text, system_prompt, api_key)


# ── providers ─────────────────────────────────────────────────────────

def _openai(text: str, system_prompt: str, api_key: str) -> str:
    import openai
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": text},
        ],
        max_tokens=1024,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


def _groq(text: str, system_prompt: str, api_key: str) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": text},
        ],
        max_tokens=1024,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

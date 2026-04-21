"""Text processing for Plus / Rage / Emoji modes.

Provider is detected from the API key prefix (same logic as transcriber.py):
  sk-...   → OpenAI  (model: gpt-4o-mini)
  gsk_...  → Groq    (model: llama-3.1-8b-instant)
"""
from __future__ import annotations
import re


def apply_snippets(text: str, snippets: list) -> str:
    """Ersetzt Keywords durch den definierten Snippet-Text (case-insensitive, ganze Wörter)."""
    for snippet in snippets:
        keyword = snippet.get("keyword", "").strip()
        replacement = snippet.get("text", "").strip()
        if not keyword or not replacement:
            continue
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(replacement, text)
    return text


def process(text: str, mode: str, api_key: str,
            prompt_template: str, emoji_density: int = 5,
            model: str | None = None,
            temperature: float = 0.7,
            max_tokens: int = 1024) -> str:
    """Transform *text* for the given mode. Normal mode is a no-op."""
    if mode == "normal":
        return text

    system_prompt = prompt_template
    if "{density}" in system_prompt:
        system_prompt = system_prompt.replace("{density}", str(emoji_density))

    if api_key.startswith("gsk_"):
        return _groq(text, system_prompt, api_key,
                     model or "llama-3.1-8b-instant", temperature, max_tokens)
    return _openai(text, system_prompt, api_key,
                   model or "gpt-4o-mini", temperature, max_tokens)


# ── providers ─────────────────────────────────────────────────────────

def _openai(text: str, system_prompt: str, api_key: str,
            model: str = "gpt-4o-mini", temperature: float = 0.7,
            max_tokens: int = 1024) -> str:
    import openai
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": text},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def _groq(text: str, system_prompt: str, api_key: str,
          model: str = "llama-3.1-8b-instant", temperature: float = 0.7,
          max_tokens: int = 1024) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": text},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()

"""LLM client — supports DeepSeek, Gemini, OpenAI-compatible, and local servers."""
import json
import logging
import os
from typing import Optional
import requests

log = logging.getLogger("aime-agent.llm")

LLM_PROVIDER = os.getenv("AIME_LLM_PROVIDER", "stub").lower()
LLM_BASE_URL = os.getenv("AIME_LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("AIME_LLM_API_KEY", "")
LLM_MODEL = os.getenv("AIME_LLM_MODEL", "")

PROVIDER_DEFAULTS = {
    "deepseek":   {"base_url": "https://api.deepseek.com",                                "model": "deepseek-chat"},
    "openai":     {"base_url": "https://api.openai.com/v1",                               "model": "gpt-4o-mini"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash"},
    "groq":       {"base_url": "https://api.groq.com/openai/v1",                          "model": "llama-3.3-70b-versatile"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",                            "model": "deepseek/deepseek-chat"},
    "local":      {"base_url": "http://127.0.0.1:8000/v1",                                "model": "local"},
}

def _resolve():
    d = PROVIDER_DEFAULTS.get(LLM_PROVIDER, {})
    return {"base_url": LLM_BASE_URL or d.get("base_url", ""), "model": LLM_MODEL or d.get("model", "")}

def chat(messages: list, max_tokens: int = 400, temperature: float = 0.7) -> Optional[str]:
    if LLM_PROVIDER == "stub":
        return None
    cfg = _resolve()
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"
    body = {"model": cfg["model"], "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    try:
        r = requests.post(url, json=body, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning("LLM call failed (%s): %s", LLM_PROVIDER, e)
        return None

def chat_json(messages: list, max_tokens: int = 400, temperature: float = 0.5) -> Optional[dict]:
    text = chat(messages, max_tokens=max_tokens, temperature=temperature)
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(text[s:e+1])
            except Exception:
                pass
        log.warning("LLM returned non-JSON: %s", text[:200])
        return None

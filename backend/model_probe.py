import os

import litellm

models = [
    "gemini/gemini-2.0-flash",
    "gemini/gemini-2.0-flash-lite",
    "gemini/gemini-2.5-flash",
    "groq/llama-3.3-70b-versatile",
    "groq/llama-3.1-8b-instant",
]

gk = os.getenv("GEMINI_API_KEY1")
rk = os.getenv("GROQ_API_KEY1")

for model in models:
    key = gk if model.startswith("gemini/") else rk
    print("TRY", model, flush=True)
    try:
        resp = litellm.completion(
            model=model,
            api_key=key,
            messages=[{"role": "user", "content": "Reply with OK"}],
            max_tokens=5,
            temperature=0,
            timeout=8,
        )
        text = resp.choices[0].message.content if resp and resp.choices else None
        print("OK", model, "|", repr(text), flush=True)
    except Exception as exc:
        print("ERR", model, "|", type(exc).__name__, "|", str(exc)[:220], flush=True)

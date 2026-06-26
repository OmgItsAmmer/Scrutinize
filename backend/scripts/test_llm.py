import requests

from app.core.config import get_settings

settings = get_settings()

models_to_test = [
    (settings.local_llm_gate_model, settings.local_llm_gate_url),
    (settings.local_llm_rewriter_model, settings.local_llm_rewriter_url),
    (settings.local_llm_decision_model, settings.local_llm_decision_url),
]

for model, url in models_to_test:
    if not url:
        print(f"Skipping {model} because no URL is configured.")
        continue
        
    if not url.endswith("/v1/chat/completions"):
        url = f"{url.rstrip('/')}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict assistant. Output only final answers. No reasoning."
            },
            {
                "role": "user",
                "content": "What is 2+2?"
            }
        ],
        "temperature": 0.7
    }

    print(f"\nTesting URL: {url} with model {model}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        print("===== MODEL OUTPUT =====")
        print(data["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"===== ERROR =====")
        print(f"Failed to test {model} at {url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(e.response.json())
            except:
                print(e.response.text)
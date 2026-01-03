# -*- coding: utf-8 -*-
import requests

class OllamaClient:
    def __init__(self, base_url="http://127.0.0.1:11434", model="deepseek-r1:latest", timeout=120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, prompt, system="Tu es l'assistant Voye. Réponses courtes et utiles.", temperature=0.2):
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return (data.get("message") or {}).get("content", "")

"""Smoke test for the LM Studio local OpenAI-compatible server.

Run from `ai/`:

    uv run python lmstudio_smoke.py

It verifies:
- `/v1/models` is reachable;
- chat completion returns non-empty Traditional Chinese content;
- embeddings return a non-empty vector;
- chat and embedding identifiers can be used back-to-back.

It does not call any cloud API.
"""

from __future__ import annotations

import os

import httpx

BASE = os.getenv("AI_LOCAL_BASE", "http://127.0.0.1:1234/v1")
CHAT_MODEL = os.getenv("AI_LOCAL_MODEL", "chat-main")
EMBED_MODEL = os.getenv("AI_EMBED_MODEL", "embed-main")


def main() -> int:
    with httpx.Client(timeout=240.0) as client:
        models = client.get(f"{BASE}/models")
        models.raise_for_status()
        ids = [item["id"] for item in models.json()["data"]]
        print("models:", ids)
        assert CHAT_MODEL in ids, f"missing chat model {CHAT_MODEL}"
        assert EMBED_MODEL in ids, f"missing embedding model {EMBED_MODEL}"

        chat = client.post(
            f"{BASE}/chat/completions",
            json={
                "model": CHAT_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": "用繁體中文，一句話說明你是什麼模型。",
                    }
                ],
                "max_tokens": 400,
                "temperature": 0.2,
            },
        )
        chat.raise_for_status()
        body = chat.json()
        content = body["choices"][0]["message"].get("content") or ""
        print("chat finish:", body["choices"][0]["finish_reason"])
        print("chat content:", content)
        assert content.strip(), "chat content is empty (increase max_tokens)"
        assert "Gemma" in content or "語言模型" in content

        embedding = client.post(
            f"{BASE}/embeddings",
            json={"model": EMBED_MODEL, "input": "食品營養成分查詢"},
        )
        embedding.raise_for_status()
        vector = embedding.json()["data"][0]["embedding"]
        print("embedding dims:", len(vector))
        assert len(vector) > 0

        # Interleave one more chat after embedding; both should stay usable.
        second = client.post(
            f"{BASE}/chat/completions",
            json={
                "model": CHAT_MODEL,
                "messages": [{"role": "user", "content": "回答一個字：好"}],
                "max_tokens": 200,
                "temperature": 0.0,
            },
        )
        second.raise_for_status()
        print("second chat finish:", second.json()["choices"][0]["finish_reason"])

    print("LM STUDIO SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

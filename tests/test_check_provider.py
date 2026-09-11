import json
import sys
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_provider  # noqa: E402

BASE = "https://llm.test/v1"


def _sse(chunks: list[dict]) -> bytes:
    body = "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks)
    return (body + "data: [DONE]\n\n").encode()


def _chunk(content: str | None = None, usage: dict | None = None) -> dict:
    choices = [] if content is None else [{"index": 0, "delta": {"content": content}}]
    return {
        "id": "c1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "m",
        "choices": choices,
        "usage": usage,
    }


def _handler(request: httpx2.Request) -> httpx2.Response:
    payload = json.loads(request.content)
    if payload.get("stream"):
        stream = _sse(
            [
                _chunk("برداشت "),
                _chunk("در چرخه‌ی پایا."),
                _chunk(usage={"prompt_tokens": 40, "completion_tokens": 9, "total_tokens": 49}),
            ]
        )
        return httpx2.Response(200, content=stream, headers={"content-type": "text/event-stream"})
    content = '{"intent": "wants_human", "search_query": "", "language": "fa"}'
    return httpx2.Response(
        200,
        json={
            "id": "c2",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
        },
    )


def test_check_provider_against_fake_server(monkeypatch, capsys):
    # openai>=3 uses httpx2, so we inject a mock transport instead of respx.
    monkeypatch.setenv("LLM_BASE_URL", BASE)
    monkeypatch.setenv("LLM_API_KEY", "k")
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(_handler))

    code = check_provider.main(["-m", "m", "--runs", "2"], http_client=client)

    out = capsys.readouterr().out
    assert code == 0
    assert "| `m` | ✅ | ✅ | native |" in out
    assert "برداشت در چرخه‌ی پایا." in out


def test_check_provider_requires_env(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(check_provider, "load_dotenv", lambda: None)
    assert check_provider.main(["-m", "m"]) == 2

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import SecretStr

from cascadegraph_runtime import ai
from cascadegraph_runtime.ai_connection import OwnAIConnection, connection_from_headers
from cascadegraph_runtime.security import InputError

CANARY = "test-only-api-key-canary-never-a-real-credential"


def headers(provider="openai", model="gpt-5.4-mini", key=CANARY):
    return {"x-cascadegraph-ai-provider": provider, "x-cascadegraph-ai-model": model, "x-cascadegraph-ai-key": key}


def test_credentials_are_masked_and_fixed_origins_cannot_be_overridden():
    config = connection_from_headers(headers(), True)
    assert config.base_url == "https://api.openai.com/v1"
    assert CANARY not in repr(config)
    for invalid in (headers(provider="https://127.0.0.1"), headers(model="bad\nmodel"), headers(key="short")):
        with pytest.raises(InputError) as exc:
            connection_from_headers(invalid, True)
        assert CANARY not in str(exc.value)
    with pytest.raises(InputError):
        connection_from_headers(headers(), False)
    assert connection_from_headers({}, False) is None


def test_own_keys_work_without_managed_keys_and_remain_request_local(monkeypatch):
    seen = []

    def transport(request):
        seen.append((request.url.host, request.headers["authorization"], json.loads(request.content)["model"]))
        return httpx.Response(200, json={"id": "test-completion", "object": "chat.completion", "created": 1,
            "model": "test-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"max_total_attempts": 3, "base_delay_ms": 25,
                    "retry_on": ["exception", "timeout", "connect", "5xx"], "evidence_lines": [1, 2],
                    "confidence": "test"})}}]})

    def sdk(**kwargs):
        assert kwargs["http_client"].follow_redirects is False
        kwargs["http_client"] = httpx.AsyncClient(transport=httpx.MockTransport(transport), follow_redirects=False)
        return AsyncOpenAI(**kwargs)

    monkeypatch.setattr(ai, "AsyncOpenAI", sdk)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("AI_INTEGRATIONS_OPENAI_API_KEY", raising=False)

    async def run():
        first = OwnAIConnection("openai", "test-openai-model", SecretStr(CANARY))
        second = OwnAIConnection("openrouter", "test/model", SecretStr(CANARY + "-other-user"))
        return await asyncio.gather(ai.OpenAIProvider(first).extract("source"),
                                    ai.OpenAIProvider(second).extract("source"))
    assert all(result.max_total_attempts == 3 for result in asyncio.run(run()))
    assert ("api.openai.com", "Bearer " + CANARY, "test-openai-model") in seen
    assert ("openrouter.ai", "Bearer " + CANARY + "-other-user", "test/model") in seen


def test_own_credentials_never_enter_analysis_report_or_logs(client, monkeypatch, caplog):
    used = []

    class FakeProvider:
        def __init__(self, connection):
            used.append(connection)

        async def extract(self, numbered):
            # Even a malicious upstream error containing the key is not exposed.
            raise RuntimeError(CANARY)

    monkeypatch.setattr("cascadegraph_runtime.app.OpenAIProvider", FakeProvider)
    response = client.post("/api/v1/analyses", json={"source_type": "sample", "use_ai": True}, headers=headers())
    assert response.status_code == 201
    assert used[0].api_key.get_secret_value() == CANARY
    assert CANARY not in response.text
    report = client.get(f"/api/v1/analyses/{response.json()['id']}/report")
    assert report.status_code == 200
    assert CANARY not in report.text
    assert CANARY not in caplog.text


def test_invalid_configuration_is_not_saved_or_echoed(client):
    response = client.post("/api/v1/analyses", json={"source_type": "sample", "use_ai": True},
                           headers=headers(provider="not-a-provider"))
    assert response.status_code == 422
    assert CANARY not in response.text
    assert client.get("/api/v1/analyses").json() == []


def test_upstream_credential_failure_has_actionable_message_without_raw_response(monkeypatch):
    def sdk(**kwargs):
        transport = httpx.MockTransport(lambda request: httpx.Response(401, json={
            "error": {"message": CANARY, "type": "invalid_api_key", "code": "invalid_api_key"}}))
        kwargs["http_client"] = httpx.AsyncClient(transport=transport)
        return AsyncOpenAI(**kwargs)
    monkeypatch.setattr(ai, "AsyncOpenAI", sdk)
    provider = ai.OpenAIProvider(connection_from_headers(headers(), True))
    from cascadegraph_runtime.ai_connection import ProviderRequestError
    with pytest.raises(ProviderRequestError) as exc:
        asyncio.run(provider.extract("source"))
    assert "Check AI settings" in str(exc.value)
    assert CANARY not in str(exc.value)

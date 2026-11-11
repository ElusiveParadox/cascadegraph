"""Request-local, non-persistent user credentials for fixed AI provider origins."""

import os
import re
from dataclasses import dataclass
from typing import Mapping

from pydantic import SecretStr

from .security import InputError

PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "gpt-5.4-mini"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-5.4-mini"),
}

class ProviderRequestError(Exception):
    """Only fixed, non-sensitive error messages may reach an evidence report."""

    def __init__(self, code: str):
        messages = {
            "credentials": "AI provider rejected the API key or its permissions. Check AI settings.",
            "model": "AI model was not found or is not available to this key. Check the model ID in AI settings.",
            "quota": "AI provider rate limit or quota was reached. Check your provider account before retrying.",
            "format": "AI provider rejected structured extraction. Choose a model supporting strict JSON-schema outputs.",
        }
        super().__init__(messages.get(code, "AI provider could not be reached or is unavailable. Try again later."))


@dataclass(frozen=True)
class OwnAIConnection:
    provider: str
    model: str
    api_key: SecretStr

    @property
    def base_url(self) -> str:
        return PROVIDERS[self.provider][0]


def connection_from_headers(headers: Mapping[str, str], use_ai: bool) -> OwnAIConnection | None:
    provider = headers.get("x-cascadegraph-ai-provider", "")
    model = headers.get("x-cascadegraph-ai-model", "")
    key = headers.get("x-cascadegraph-ai-key", "")
    if not any((provider, model, key)):
        return None
    if not use_ai:
        raise InputError("Custom AI credentials require explicit AI opt-in.")
    if os.getenv("LLM_ENABLED", "true").lower() != "true":
        raise InputError("AI extraction is disabled by this server.")
    if provider not in PROVIDERS:
        raise InputError("Choose OpenAI or OpenRouter in AI settings.")
    if not re.fullmatch(r"[!-~]{10,1024}", key):
        raise InputError("Enter a valid API key in AI settings.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,149}", model):
        raise InputError("Enter a valid model ID in AI settings.")
    return OwnAIConnection(provider, model, SecretStr(key))

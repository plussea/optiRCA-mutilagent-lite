import json
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from optirc_lite.config import settings


class LLMTool:
    """OpenAI-compatible LLM wrapper used by skills.

    The base URL is normalized because users often paste either the API root
    or the full `/chat/completions` endpoint into `.env`.
    """

    def __init__(self) -> None:
        self._client: Optional[AsyncOpenAI] = None

    def enabled(self) -> bool:
        return bool(settings.llm_api_key and settings.llm_model)

    async def generate_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        if not self.enabled():
            raise RuntimeError("LLM is not configured. Set LLM_API_KEY and LLM_MODEL.")

        client = self._get_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{system}\n\n"
                        "Return valid JSON only. Do not wrap the response in markdown."
                    ),
                },
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content or "{}"
        return self._parse_json(content)

    async def generate_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> str:
        if not self.enabled():
            raise RuntimeError("LLM is not configured. Set LLM_API_KEY and LLM_MODEL.")

        client = self._get_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=self._normalize_base_url(settings.llm_base_url),
                timeout=settings.llm_timeout_seconds,
            )
        return self._client

    @staticmethod
    def _normalize_base_url(url: str) -> str | None:
        value = (url or "").strip().rstrip("/")
        if not value:
            return None
        for suffix in ("/chat/completions", "/v1/chat/completions"):
            if value.endswith(suffix):
                value = value[: -len(suffix)]
                break
        return value.rstrip("/") or None

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return json.loads(text)


llm_tool = LLMTool()

"""One OpenAI-compatible chat call per decision, raw reply kept for audit.

Backends are data, not code: base URL, model, the environment variable that
holds the key, and extra headers. Keys are read from the environment and never
written to the call record.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BACKENDS = {
    # Native API: the OpenAI-compatible route ignores num_ctx and truncates at 4096 tokens.
    "ollama": {"base_url": "http://127.0.0.1:11434", "key_env": None, "native": True,
               "extra_body": {"think": False, "format": "json", "options": {"num_ctx": 32768}}},
    "opencode_go": {"base_url": "https://opencode.ai/inference/go/openai/v1",
                    "key_env": "OPENCODE_API_KEY", "session_header": "x-opencode-session"},
}


class LLMError(RuntimeError):
    """Transport failure or a reply without one JSON object."""


class LLMReplyError(LLMError):
    """The provider answered, but generation did not produce a usable reply."""


class LLMProviderError(LLMError):
    """The provider explicitly reported an error, including inside an SSE stream."""


def extract_json(text: str) -> dict:
    """The reply's JSON object, allowing one fenced block around it."""
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, re.S)
    body = fenced.group(1) if fenced else text.strip()
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("reply is not a JSON object")
    return value


class Client:
    def __init__(self, backend: str, model: str, *, timeout_s: float = 300.,
                 temperature: float | None = None, max_tokens: int | None = None,
                 thinking: str | None = None, json_mode: bool = False):
        self.backend, self.model, self.timeout_s = backend, model, timeout_s
        self.config = BACKENDS[backend]
        self.temperature, self.max_tokens = temperature, max_tokens
        if thinking not in (None, 'enabled', 'disabled'):
            raise ValueError('thinking must be enabled, disabled or None')
        self.thinking = thinking
        self.json_mode = json_mode
        key_env = self.config["key_env"]
        self.key = os.environ[key_env] if key_env else "ollama"
        self.session = "growup-" + uuid.uuid4().hex

    def _stream(self, request, record: Path) -> tuple[str, dict | None, str | None]:
        """Server-sent events; keeps long reasoning replies alive past proxy idle limits."""
        parts, usage, finish = [], None, None
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response, \
                (record / "stream.jsonl").open("x", encoding="utf-8") as log:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                log.write(data + "\n")
                if 'error' in event and event['error'] is not None:
                    raise LLMProviderError('provider stream error: ' + json.dumps(event['error'])[:500])
                usage = event.get("usage") or usage
                for choice in event.get("choices", []):
                    parts.append(choice.get("delta", {}).get("content") or "")
                    finish = choice.get("finish_reason") or finish
        text = "".join(parts)
        (record / "reply.txt").write_text(text)
        return text, usage, finish

    def _stream_native(self, request, record: Path) -> tuple[str, dict | None, str | None]:
        """Ollama /api/chat newline-delimited JSON stream."""
        parts, usage, finish = [], None, None
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response, \
                (record / "stream.jsonl").open("x", encoding="utf-8") as log:
            for raw in response:
                if not raw.strip():
                    continue
                event = json.loads(raw)
                log.write(raw.decode().strip() + "\n")
                parts.append(event.get("message", {}).get("content") or "")
                if event.get("done"):
                    finish = event.get("done_reason")
                    usage = {"prompt_tokens": event.get("prompt_eval_count"),
                             "completion_tokens": event.get("eval_count")}
        text = "".join(parts)
        (record / "reply.txt").write_text(text)
        return text, usage, finish

    def describe(self) -> dict:
        return {"backend": self.backend, "model": self.model, "base_url": self.config["base_url"],
                "temperature": self.temperature, "max_tokens": self.max_tokens,
                "timeout_s": self.timeout_s, 'thinking': self.thinking, 'json_mode': self.json_mode}

    def chat(self, system: str, user: str, record: Path) -> tuple[dict, dict]:
        """Return the parsed JSON object and usage; write the exchange to ``record``."""
        record.mkdir(parents=True, exist_ok=False)
        body = {"model": self.model, "messages": [{"role": "system", "content": system},
                                                  {"role": "user", "content": user}],
                "stream": True, "stream_options": {"include_usage": True},
                **self.config.get("extra_body", {})}
        native = self.config.get("native", False)
        if self.thinking is not None:
            body['thinking'] = {'type': self.thinking}
        if self.json_mode and not native:
            body['response_format'] = {'type': 'json_object'}
        if native:
            body.pop("stream_options")
            body["options"] = dict(body.get("options", {}))
            if self.temperature is not None:
                body["options"]["temperature"] = self.temperature
            if self.max_tokens is not None:
                body["options"]["num_predict"] = self.max_tokens
        else:
            if self.temperature is not None:
                body["temperature"] = self.temperature
            if self.max_tokens is not None:
                body["max_tokens"] = self.max_tokens
        (record / "request.json").write_text(json.dumps({**body, "client": self.describe()},
                                                        ensure_ascii=False, indent=1))
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.key,
                   "User-Agent": "growup-harness/0.1"}
        if "session_header" in self.config:
            headers[self.config["session_header"]] = self.session
        path = "/api/chat" if native else "/chat/completions"
        request = urllib.request.Request(self.config["base_url"] + path,
                                         json.dumps(body).encode(), headers)
        started = time.monotonic()
        meta = {"client": self.describe()}
        try:
            try:
                text, usage, finish = (self._stream_native if native else self._stream)(request, record)
            except urllib.error.HTTPError as error:
                raise LLMProviderError(f"HTTP {error.code}: {error.read()[:500]!r}") from None
            except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError) as error:
                raise LLMError(f"transport: {type(error).__name__}: {error}") from None
            meta.update(usage=usage, finish_reason=finish)
            if finish == 'length':
                meta['failure_kind'] = 'generation_limit'
                raise LLMReplyError('generation reached the output-token limit')
            try:
                decision = extract_json(text)
            except ValueError as error:
                meta['failure_kind'] = 'response_schema'
                raise LLMReplyError(f"reply is not one JSON object: {error}") from None
            meta["status"] = "ok"
            return decision, meta
        except LLMError as error:
            meta.update(status="error", error=str(error))
            if isinstance(error, LLMProviderError):
                meta['failure_kind'] = 'provider'
            elif not isinstance(error, LLMReplyError):
                meta['failure_kind'] = 'transport'
            raise
        finally:
            meta["wall_seconds"] = time.monotonic() - started
            (record / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))

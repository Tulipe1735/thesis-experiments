"""Read the authorized example without executing it; never persist its credential."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


class GatewayError(RuntimeError):
    def __init__(self, status, message, *, seconds=0.0, retry_after=None):
        super().__init__(message)
        self.status = status
        self.seconds = seconds
        self.retry_after = retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the user's Authorization header to another origin.
        return None


@dataclass(repr=False)
class AstraGateway:
    base_url: str
    model: str
    _key: str = field(repr=False)

    @classmethod
    def from_example(cls, source: Path):
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        values = {}
        models = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == 'OpenAI':
                for kw in node.keywords:
                    if kw.arg in ('base_url', 'api_key') and isinstance(kw.value, ast.Constant):
                        values[kw.arg] = kw.value.value
            for kw in node.keywords:
                if kw.arg == 'model' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    models.add(kw.value.value)
        if len(models) != 1 or not all(isinstance(values.get(k), str) and values[k] for k in ['base_url', 'api_key']):
            raise ValueError('Example must contain one literal model and a literal OpenAI base_url/api_key')
        url = urllib.parse.urlsplit(values['base_url'])
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Unsupported gateway URL')
        return cls(values['base_url'].rstrip('/'), models.pop(), values['api_key'])

    def __repr__(self):
        return f'AstraGateway(model={self.model!r}, credential=[REDACTED])'

    def request(self, route: str, payload=None):
        if route not in ('/models', '/chat/completions', '/responses'):
            raise ValueError('Unapproved gateway route')
        headers = {'Authorization': 'Bearer ' + self._key}
        raw = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        req = urllib.request.Request(self.base_url + route, data=raw, headers=headers)
        start = time.monotonic()
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=55) as response:
                data = json.load(response)
                return data, time.monotonic() - start
        except urllib.error.HTTPError as exc:
            message = exc.read(2000).decode(errors='replace').replace(self._key, '[REDACTED]')
            raise GatewayError(exc.code, message, seconds=time.monotonic() - start,
                               retry_after=exc.headers.get('Retry-After')) from None
        except (OSError, ValueError, urllib.error.URLError) as exc:
            raise GatewayError(None, str(exc).replace(self._key, '[REDACTED]'),
                               seconds=time.monotonic() - start) from None

    def chat(self, messages, **kwargs):
        return self.request('/chat/completions', {'model': self.model, 'messages': messages, **kwargs})

    def responses(self, inputs, **kwargs):
        return self.request('/responses', {'model': self.model, 'input': inputs, 'store': False, **kwargs})

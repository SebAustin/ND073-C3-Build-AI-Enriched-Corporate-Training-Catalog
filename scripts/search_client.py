"""Minimal Azure AI Search REST client (stdlib only) shared by the project scripts.

Configuration comes from the environment so no key is ever written to disk:
  SEARCH_ENDPOINT   e.g. https://tcat-search-ab12.search.windows.net
  SEARCH_ADMIN_KEY  admin key (Keys blade)
"""

from __future__ import annotations

import copy
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

API_VERSION = "2024-07-01"

# Names agreed in the design (see docs/adr and GLOSSARY.md).
COURSES = {"datasource": "course-data", "index": "courses-index",
           "skillset": "courses-skillset", "indexer": "courses-indexer"}
LIBRARY = {"datasource": "research-library", "index": "library-index",
           "skillset": "library-skillset", "indexer": "library-indexer"}

SECRET_PLACEHOLDERS = (
    (re.compile(r"([?&]code=)[^&\"]+"), r"\1<function-key>"),
    (re.compile(r"(AccountKey=)[^;\"]+"), r"\1<storage-account-key>"),
    (re.compile(r"(SharedAccessSignature=)[^;\"]+"), r"\1<sas-token>"),
)
SECRET_KEYS = {"key", "apiKey", "connectionString"}


class SearchError(RuntimeError):
    """Raised when the Search service rejects a request."""


def _config() -> tuple[str, str]:
    endpoint = os.environ.get("SEARCH_ENDPOINT", "").rstrip("/")
    key = os.environ.get("SEARCH_ADMIN_KEY", "")
    if not endpoint or not key:
        raise SystemExit("Set SEARCH_ENDPOINT and SEARCH_ADMIN_KEY first.")
    return endpoint, key


def request(method: str, path: str, body: Any = None) -> Any:
    endpoint, key = _config()
    separator = "&" if "?" in path else "?"
    url = f"{endpoint}/{path.lstrip('/')}{separator}api-version={API_VERSION}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise SearchError(f"{method} {path} -> {exc.code}: {detail}") from exc


def get(kind: str, name: str) -> dict:
    return request("GET", f"{kind}/{name}")


def put(kind: str, name: str, definition: dict) -> dict | None:
    body = {k: v for k, v in definition.items() if k != "@odata.etag"}
    return request("PUT", f"{kind}/{name}", body)


def scrub(definition: Any) -> Any:
    """Return a copy of a definition with secrets replaced by placeholders."""
    def walk(node: Any, key: str | None = None) -> Any:
        if isinstance(node, dict):
            return {k: walk(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            if key in SECRET_KEYS and node and not node.startswith("<"):
                return f"<{key}>"
            for pattern, replacement in SECRET_PLACEHOLDERS:
                node = pattern.sub(replacement, node)
        return node
    return walk(copy.deepcopy(definition))

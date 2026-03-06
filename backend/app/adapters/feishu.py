"""
Feishu reader adapter.
Thin wrapper around the Feishu doc/wiki reading logic
ported from canonical_frontend/canonical/adapters/feishu.py.
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List

import requests

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _FeishuReadError:
    endpoint: str
    code: int
    msg: str
    request_id: Optional[str] = None


class _FeishuClient:
    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    def _get_access_token(self) -> str:
        now = datetime.utcnow()
        if self._access_token and self._token_expires and now < self._token_expires:
            return self._access_token
        resp = requests.post(
            f"{self.BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=settings.feishu_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"Feishu token error: {data.get('msg')}")
        self._access_token = data["tenant_access_token"]
        self._token_expires = now + timedelta(hours=1, minutes=30)
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._get_access_token()}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, **kwargs) -> Tuple[Optional[Dict], Optional[_FeishuReadError]]:
        timeout = settings.feishu_timeout
        for _ in range(settings.feishu_retry + 1):
            try:
                resp = requests.request(method, url, headers=self._headers(), timeout=timeout, **kwargs)
                data = resp.json() if resp.content else {}
                rid = resp.headers.get("X-Request-Id") or data.get("request_id")
                if resp.status_code >= 400 or data.get("code", 0) != 0:
                    return None, _FeishuReadError(url, data.get("code", resp.status_code), data.get("msg", ""), rid)
                return data, None
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as e:
                return None, _FeishuReadError(url, -1, str(e))
        return None, _FeishuReadError(url, -1, "Max retries exceeded")

    def get_doc_metadata(self, doc_id: str):
        data, err = self._request("GET", f"{self.BASE_URL}/docx/v1/documents/{doc_id}")
        return (data.get("data") if data else None, err)

    def get_doc_raw_content(self, doc_id: str):
        data, err = self._request("GET", f"{self.BASE_URL}/docx/v1/documents/{doc_id}/raw_content")
        return ((data or {}).get("data", {}).get("content", ""), err)

    def get_wiki_node_by_token(self, token: str):
        data, err = self._request("GET", f"{self.BASE_URL}/wiki/v2/spaces/get_node?token={token}")
        return ((data or {}).get("data", {}).get("node"), err)


def _resolve_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract doc_type and token from a Feishu URL."""
    m = re.search(r"feishu\.cn/docx/([A-Za-z0-9]+)", url)
    if m:
        return "docx", m.group(1)
    m = re.search(r"feishu\.cn/docs/([A-Za-z0-9]+)", url)
    if m:
        return "docs", m.group(1)
    m = re.search(r"feishu\.cn/wiki/([A-Za-z0-9]+)", url)
    if m:
        return "wiki", m.group(1)
    return None, None


class FeishuReaderAdapter:
    """Read Feishu doc/wiki content and return plain text."""

    def __init__(self):
        self._client = _FeishuClient()

    def read(self, url: str) -> Dict[str, Any]:
        if not self._client.configured:
            return {"title": "", "plain_text": "", "error": "Feishu credentials not configured"}

        doc_type, token = _resolve_url(url)
        if not token:
            return {"title": "", "plain_text": "", "error": f"Cannot parse Feishu URL: {url}"}

        doc_id = token
        if doc_type == "wiki":
            node, err = self._client.get_wiki_node_by_token(token)
            if err:
                return {"title": "", "plain_text": "", "error": err.msg}
            if node:
                obj_token = node.get("obj_token")
                if obj_token and node.get("obj_type") in ("doc", "docx"):
                    doc_id = obj_token
                else:
                    return {"title": node.get("title", ""), "plain_text": "", "error": "Unsupported wiki node type"}

        meta, err = self._client.get_doc_metadata(doc_id)
        title = (meta or {}).get("title", "")
        raw, err = self._client.get_doc_raw_content(doc_id)
        if err:
            return {"title": title, "plain_text": "", "error": err.msg}
        return {"title": title, "plain_text": (raw or "").strip(), "source_url": url}

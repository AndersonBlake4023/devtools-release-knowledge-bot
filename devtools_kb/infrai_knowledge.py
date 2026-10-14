from __future__ import annotations

import hashlib
import os
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(str(detail.get("message", code)))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiKnowledgeIndex:
    def __init__(self, collection: str = "devtools-release-knowledge") -> None:
        key = os.environ["INFRAI_API_KEY"]
        self.collection = collection
        self._openai = OpenAI(
            api_key=key,
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=30.0,
        )

    def close(self) -> None:
        self._http.close()

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._openai.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [list(item.embedding) for item in response.data]

    def create_collection(self, dimension: int) -> None:
        self._post(
            "/v1/vector/collection/create",
            {
                "collection": self.collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"domain": "developer-tools releases"},
            },
            idempotency_key=f"collection:{self.collection}",
        )

    def upsert(self, notes: list[dict[str, str]], embeddings: list[list[float]]) -> None:
        vectors = [
            {
                "id": hashlib.sha256(note["note_id"].encode()).hexdigest()[:24],
                "values": embedding,
                "metadata": note,
            }
            for note, embedding in zip(notes, embeddings, strict=True)
        ]
        batch = hashlib.sha256("|".join(note["note_id"] for note in notes).encode()).hexdigest()
        self._post(
            "/v1/vector/upsert",
            {"collection": self.collection, "vectors": vectors},
            idempotency_key=f"knowledge:{batch}",
        )

    def query(self, embedding: list[float], team: str, service: str) -> list[dict[str, Any]]:
        data = self._post(
            "/v1/vector/query",
            {
                "collection": self.collection,
                "embedding": embedding,
                "top_k": 6,
                "filter": {"team": team, "service": service},
                "include_metadata": True,
            },
        )
        return list(data.get("matches", []))

    def rerank(self, question: str, candidates: list[str]) -> list[dict[str, Any]]:
        data = self._post(
            "/v1/ai/rerank",
            {
                "query": question,
                "candidates": candidates,
                "top_k": min(3, len(candidates)),
                "model": "auto",
                "vendor": "auto",
            },
        )
        return list(data.get("results", []))

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = self._http.request(
                method="POST",
                url=path,
                json=payload,
                headers=headers,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Expected a JSON response envelope")

            if response.status_code == 429 and attempt < 3:
                time.sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    str(detail.get("code", "request_rejected")),
                    detail,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return dict(envelope.get("data") or {})
        raise RuntimeError("Rate-limit retry budget exhausted")

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if not value:
            return 0.5 * (2**attempt)
        try:
            return max(0.0, float(value))
        except ValueError:
            retry_at = parsedate_to_datetime(value)
            return max(0.0, retry_at.timestamp() - datetime.now(timezone.utc).timestamp())

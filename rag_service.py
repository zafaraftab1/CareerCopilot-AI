"""
RAG service with local vector storage and Ollama embeddings.
"""
from __future__ import annotations

import math
import hashlib
from typing import Dict, List, Tuple, Optional

import requests

from models import db, RagDocument


class RagService:
    """Build and query a lightweight vector DB for jobs and profile context."""

    def __init__(self, app_config):
        self.config = app_config
        self.base_url = (app_config.get('OLLAMA_BASE_URL') or 'http://127.0.0.1:11434').rstrip('/')
        self.model = app_config.get('OLLAMA_MODEL', 'llama3.2:3b')
        self.embedding_model = app_config.get('OLLAMA_EMBED_MODEL', self.model)

    def _fallback_embedding(self, text: str, dims: int = 256) -> List[float]:
        """Deterministic local embedding when Ollama embedding endpoint is unavailable."""
        vector = [0.0] * dims
        for token in (text or '').lower().split():
            idx = int(hashlib.sha256(token.encode('utf-8')).hexdigest(), 16) % dims
            vector[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_text(self, text: str) -> List[float]:
        payload = {
            "model": self.embedding_model,
            "prompt": text or ""
        }
        try:
            response = requests.post(f"{self.base_url}/api/embeddings", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            embedding = data.get('embedding') or []
            if embedding:
                return embedding
        except Exception:
            pass
        return self._fallback_embedding(text)

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        n = min(len(vec1), len(vec2))
        dot = sum(vec1[i] * vec2[i] for i in range(n))
        n1 = math.sqrt(sum(vec1[i] * vec1[i] for i in range(n))) or 1.0
        n2 = math.sqrt(sum(vec2[i] * vec2[i] for i in range(n))) or 1.0
        return dot / (n1 * n2)

    def upsert_document(self, doc_type: str, doc_ref: str, content: str, metadata: Optional[Dict] = None) -> RagDocument:
        embedding = self.embed_text(content)
        doc = RagDocument.query.filter_by(doc_type=doc_type, doc_ref=doc_ref).first()
        if not doc:
            doc = RagDocument(
                doc_type=doc_type,
                doc_ref=doc_ref,
                content=content,
                embedding=embedding,
                meta_json=metadata or {}
            )
            db.session.add(doc)
        else:
            doc.content = content
            doc.embedding = embedding
            doc.meta_json = metadata or {}
        db.session.commit()
        return doc

    def index_jobs(self, jobs: List[Dict]) -> int:
        count = 0
        for job in jobs:
            ref = job.get('portal_job_id') or job.get('job_url') or f"job_{count}"
            content = (
                f"Title: {job.get('job_title', '')}\n"
                f"Company: {job.get('company', '')}\n"
                f"Location: {job.get('location', '')}\n"
                f"Experience: {job.get('experience_required', '')}\n"
                f"Skills: {', '.join(job.get('required_skills', [])[:20])}\n"
                f"Description: {job.get('description', '')}"
            )
            self.upsert_document(
                doc_type='job',
                doc_ref=ref,
                content=content,
                metadata={
                    'portal': job.get('portal'),
                    'job_url': job.get('job_url'),
                    'company': job.get('company'),
                    'job_title': job.get('job_title')
                }
            )
            count += 1
        return count

    def query(self, question: str, top_k: int = 5, doc_type: str = 'job') -> List[Tuple[float, RagDocument]]:
        query_vec = self.embed_text(question)
        docs = RagDocument.query.filter_by(doc_type=doc_type).all()
        scored = []
        for doc in docs:
            score = self.cosine_similarity(query_vec, doc.embedding or [])
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:max(1, top_k)]

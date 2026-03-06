"""
Persistent memory store backed by ChromaDB.
Tracks interviewer patterns, question history, and effective questions.
"""

import logging
from typing import Optional, List, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


class MemoryStore:
    """Vector-based persistent memory for cross-session learning."""

    def __init__(self):
        self._client = None
        self._collection = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            import chromadb
            persist_dir = str(settings.chroma_persist_dir)
            self._client = chromadb.PersistentClient(path=persist_dir)
            self._collection = self._client.get_or_create_collection(
                name="interview_memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB memory store initialised at %s", persist_dir)
        except ImportError:
            logger.warning("chromadb not installed; memory store disabled")
        except Exception:
            logger.exception("Failed to initialise ChromaDB")

    @property
    def available(self) -> bool:
        self._ensure_client()
        return self._collection is not None

    def add_question(self, question: str, session_id: str, dimension: str = "", effectiveness: str = "unknown"):
        """Record a question asked by the interviewer."""
        if not self.available:
            return
        doc_id = f"q-{session_id}-{hash(question) % 10**8}"
        self._collection.upsert(
            ids=[doc_id],
            documents=[question],
            metadatas=[{"type": "question", "session_id": session_id, "dimension": dimension, "effectiveness": effectiveness}],
        )

    def add_insight(self, insight: str, session_id: str, insight_type: str = "pattern"):
        """Record a general insight or pattern."""
        if not self.available:
            return
        doc_id = f"i-{session_id}-{hash(insight) % 10**8}"
        self._collection.upsert(
            ids=[doc_id],
            documents=[insight],
            metadatas=[{"type": insight_type, "session_id": session_id}],
        )

    def find_similar_questions(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Check if a similar question has been asked before."""
        if not self.available:
            return []
        try:
            results = self._collection.query(
                query_texts=[question],
                n_results=top_k,
                where={"type": "question"},
            )
            matches = []
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                dist = results["distances"][0][i] if results.get("distances") else None
                matches.append({"text": doc, "distance": dist, **meta})
            return matches
        except Exception:
            logger.exception("Memory query failed")
            return []

    def get_interviewer_patterns(self, top_k: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent interviewer patterns and biases."""
        if not self.available:
            return []
        try:
            results = self._collection.get(
                where={"type": "question"},
                limit=top_k,
            )
            dimension_counts: Dict[str, int] = {}
            for meta in (results.get("metadatas") or []):
                dim = meta.get("dimension", "unknown")
                dimension_counts[dim] = dimension_counts.get(dim, 0) + 1
            return [{"dimension": k, "count": v} for k, v in sorted(dimension_counts.items(), key=lambda x: -x[1])]
        except Exception:
            logger.exception("Pattern retrieval failed")
            return []

    def check_repetition(self, question: str, threshold: float = 0.15) -> Optional[str]:
        """Return the previous similar question if one exists within threshold."""
        matches = self.find_similar_questions(question, top_k=1)
        if matches and matches[0].get("distance") is not None and matches[0]["distance"] < threshold:
            return matches[0]["text"]
        return None

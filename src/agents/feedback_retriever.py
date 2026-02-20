import json
import logging
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List

from src.agents.adapter import OllamaModelAdapter
from src.config import load_config
from src.schemas.agent_artifacts import FeedbackCase

logger = logging.getLogger(__name__)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class FeedbackRetriever:
    """
    Minimal local-first feedback indexer/retriever.
    Stores embeddings + metadata in JSONL under feedback_index_path.
    """

    def __init__(
        self,
        embedding_model: str = "nomic-embed-text",
        collection_name: str = "paperpipe_feedback",
        min_similarity: float = 0.75,
    ):
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        self.min_similarity = min_similarity
        self.adapter = OllamaModelAdapter()

        persist_path = "storage/feedback_index"
        try:
            config = load_config()
            if config.agents and getattr(config.agents, "feedback_index_path", None):
                persist_path = config.agents.feedback_index_path
        except Exception as exc:
            logger.warning("FeedbackRetriever config load failed, using default path: %s", exc)

        self.persist_path = str(Path(persist_path))
        self._index_dir = Path(self.persist_path)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._index_dir / f"{self.collection_name}.jsonl"

    def add_feedback(self, case: FeedbackCase) -> bool:
        text_to_embed = (case.user_correction or "").strip()
        if not text_to_embed:
            logger.warning("FeedbackCase has no user_correction. Skipping index.")
            return False

        embedding = self.adapter.embed(text_to_embed, model=self.embedding_model)
        if not embedding:
            logger.error("Failed to embed feedback for paper_id=%s run_id=%s", case.paper_id, case.run_id)
            return False

        feedback_id = getattr(case, "feedback_id", None) or str(uuid.uuid4())
        payload: Dict[str, Any] = {
            "feedback_id": feedback_id,
            "embedding": embedding,
            "metadata": {
                "paper_id": case.paper_id,
                "run_id": case.run_id,
                "accepted": bool(case.accepted),
                "preview": text_to_embed.replace("\n", " ")[:180],
            },
            "document": text_to_embed,
        }

        try:
            with self._index_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            return True
        except Exception as exc:
            logger.error("Failed to index feedback %s: %s", feedback_id, exc)
            return False

    def query_relevant_feedback(self, query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        if not query_text:
            return []

        query_embedding = self.adapter.embed(query_text, model=self.embedding_model)
        if not query_embedding:
            logger.error("Failed to embed feedback query.")
            return []

        if not self._index_file.exists():
            return []

        scored: List[tuple[float, Dict[str, Any]]] = []
        try:
            for line in self._index_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                metadata = record.get("metadata") or {}
                if metadata.get("accepted") is not True:
                    continue

                embedding = record.get("embedding") or []
                score = _cosine_similarity(query_embedding, embedding)
                if score < self.min_similarity:
                    continue
                scored.append((score, metadata))
        except Exception as exc:
            logger.error("Error querying feedback index: %s", exc)
            return []

        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[Dict[str, Any]] = []
        for _, meta in scored[: max(0, limit)]:
            out.append({"paper_id": meta.get("paper_id"), "preview": meta.get("preview")})
        return out

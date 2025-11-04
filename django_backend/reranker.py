import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Optional cross-encoder reranker. Falls back to passthrough when model unavailable."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model = None
        try:
            from sentence_transformers import CrossEncoder  # type: ignore
            self.model = CrossEncoder(model_name)
            logger.info(f"CrossEncoderReranker loaded: {model_name}")
        except Exception as e:
            logger.warning(f"CrossEncoder not available, reranker disabled: {e}")

    def available(self) -> bool:
        return self.model is not None

    def rerank(self, query: str, docs: List[Dict], top_k: int) -> List[Dict]:
        if not self.available() or not docs:
            return docs
        pairs = [(query, d.get("content", "")) for d in docs]
        try:
            scores = self.model.predict(pairs)
            rescored: List[Tuple[float, Dict]] = list(zip(scores, docs))
            rescored.sort(key=lambda x: x[0], reverse=True)
            reranked = [d for _, d in rescored[:top_k]]
            # 将 cross-encoder 分数写回
            for i, (_, d) in enumerate(rescored):
                d["rerank_score"] = float(scores[i]) if i < len(scores) else 0.0
            return reranked
        except Exception as e:
            logger.warning(f"CrossEncoder rerank failed, fallback passthrough: {e}")
            return docs

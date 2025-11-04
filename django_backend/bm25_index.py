import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class BM25Index:
    """Optional BM25 index using rank_bm25. Falls back gracefully when unavailable."""

    def __init__(self, docs: Optional[List[str]] = None) -> None:
        self.available = False
        self.corpus_tokens: List[List[str]] = []
        self.bm25 = None
        try:
            from rank_bm25 import BM25Okapi  # type: ignore
            self._BM25Okapi = BM25Okapi
            self.available = True
        except Exception as e:
            logger.warning(f"BM25 not available, sparse retrieval disabled: {e}")
            self._BM25Okapi = None
        if docs:
            self.build(docs)

    def _tokenize(self, text: str) -> List[str]:
        # 简易分词：空白切分 + 小写
        return (text or "").lower().split()

    def build(self, docs: List[str]) -> None:
        if not self.available:
            return
        self.corpus_tokens = [self._tokenize(t) for t in docs]
        try:
            self.bm25 = self._BM25Okapi(self.corpus_tokens)
        except Exception as e:
            logger.warning(f"BM25 build failed: {e}")
            self.available = False
            self.bm25 = None

    def query(self, q: str, top_k: int = 10) -> List[Dict]:
        if not (self.available and self.bm25 and self.corpus_tokens):
            return []
        try:
            q_tokens = self._tokenize(q)
            scores = self.bm25.get_scores(q_tokens)
            idx_scores = list(enumerate(scores))
            idx_scores.sort(key=lambda x: x[1], reverse=True)
            results: List[Dict] = []
            for idx, sc in idx_scores[:top_k]:
                results.append({"index": idx, "score": float(sc)})
            return results
        except Exception as e:
            logger.warning(f"BM25 query failed: {e}")
            return []

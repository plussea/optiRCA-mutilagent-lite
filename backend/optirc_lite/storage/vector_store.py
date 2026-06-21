import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List

import lancedb

from optirc_lite.config import settings


class LanceVectorStore:
    """Embedded LanceDB vector store.

    It requires no background service. Embeddings are deterministic lightweight
    hash embeddings for now, so the storage layer is real LanceDB while the
    embedding model can later be swapped behind `_embed`.
    """

    def __init__(self, path: Path | None = None, table_name: str | None = None) -> None:
        self.path = path or settings.lancedb_path
        self.table_name = table_name or settings.lancedb_table
        self._db: Any = None
        self._table: Any = None

    def init(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.path))
        if self.table_name not in self._db.table_names():
            self._table = self._db.create_table(self.table_name, data=self._seed_records())
        else:
            self._table = self._db.open_table(self.table_name)

    def search(self, query: str, top_k: int = 5, doc_type: str | None = None) -> List[Dict[str, Any]]:
        self._ensure_ready()
        search = self._table.search(self._embed(query)).limit(top_k)
        if doc_type:
            search = search.where(f"type = '{doc_type}'", prefilter=True)
        rows = search.to_list()
        return [self._row_to_doc(row) for row in rows]

    def add(self, content: str, metadata: Dict[str, Any] | None = None) -> None:
        self._ensure_ready()
        metadata = metadata or {}
        record = {
            "id": metadata.get("id") or self._make_id(content),
            "type": metadata.get("type", "case"),
            "content": content,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
            "vector": self._embed(content),
        }
        self._table.add([record])

    def _ensure_ready(self) -> None:
        if self._table is None:
            self.init()

    def _seed_records(self) -> List[Dict[str, Any]]:
        docs = [
            {
                "id": "kb-1",
                "type": "knowledge",
                "content": "大量 LOS、MUT_LOS、光功率异常同时出现时，优先排查光纤中断、尾纤松动、ODF 跳纤和上游传输链路。",
                "metadata": {"source": "seed"},
            },
            {
                "id": "kb-2",
                "type": "knowledge",
                "content": "单设备端口误码、CRC、FEC 纠错升高，通常与光模块老化、光功率边缘、连接器污染有关。",
                "metadata": {"source": "seed"},
            },
            {
                "id": "sop-1",
                "type": "sop",
                "content": "光纤中断处理 SOP：确认告警范围，检查受影响设备，核对光功率，派单巡检光缆，准备临时倒换方案。",
                "metadata": {"source": "seed"},
            },
        ]
        return [
            {
                "id": doc["id"],
                "type": doc["type"],
                "content": doc["content"],
                "metadata_json": json.dumps(doc["metadata"], ensure_ascii=False),
                "vector": self._embed(doc["content"]),
            }
            for doc in docs
        ]

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * settings.embedding_dimension
        tokens = self._tokens(text)
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, min(len(digest), settings.embedding_dimension), 4):
                bucket = int.from_bytes(digest[offset : offset + 2], "little") % settings.embedding_dimension
                sign = 1.0 if digest[offset + 2] % 2 == 0 else -1.0
                vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

    @staticmethod
    def _make_id(content: str) -> str:
        return hashlib.sha1(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_doc(row: Dict[str, Any]) -> Dict[str, Any]:
        metadata_json = row.get("metadata_json") or "{}"
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        score = row.get("_distance")
        return {
            "id": row.get("id"),
            "type": row.get("type"),
            "content": row.get("content", ""),
            "metadata": metadata,
            "score": round(float(score), 4) if score is not None else None,
        }


vector_store = LanceVectorStore()

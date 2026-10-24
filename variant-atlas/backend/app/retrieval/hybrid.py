"""Atlas Search + Vector Search over permitted version-filtered methods passages."""
import math
import httpx
from pymongo.operations import SearchIndexModel

SEARCH_NAME = "pten_methods_text_v1"
VECTOR_NAME = "pten_methods_vector_v1"


class RetrievalUnavailable(RuntimeError):
    pass


class HybridRetrieval:
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings

    def embed(self, texts, input_type):
        s = self.settings
        if (
            s.embedding_provider != "voyage"
            or not s.voyage_api_key
            or not s.embedding_model
        ):
            raise RetrievalUnavailable(
                "Voyage embedding provider/key/exact model are required; no substitute vectors generated."
            )
        if not 1 <= len(texts) <= 64 or sum(map(len, texts)) > 120000:
            raise ValueError("Embedding input budget exceeded.")
        with httpx.Client(timeout=45) as client:
            response = client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": "Bearer " + s.voyage_api_key},
                json={
                    "input": texts,
                    "model": s.embedding_model,
                    "input_type": input_type,
                },
            )
            if response.status_code != 200:
                raise RetrievalUnavailable(
                    f"Embedding provider HTTP {response.status_code}."
                )
            body = response.json()
        vectors = [
            r["embedding"] for r in sorted(body["data"], key=lambda r: r["index"])
        ]
        if (
            len(vectors) != len(texts)
            or not vectors
            or not vectors[0]
            or any(
                len(v) != len(vectors[0]) or any(not math.isfinite(x) for x in v)
                for v in vectors
            )
        ):
            raise ValueError("Invalid embedding response.")
        return vectors, body.get("usage", {})

    def seed_embeddings(self, w):
        if self.store.db is None:
            raise ValueError("DATA_BACKEND=atlas is required.")
        docs = w["evidence"]
        usage = []
        for start in range(0, len(docs), 32):
            batch = docs[start : start + 32]
            vectors, u = self.embed([p["text"] for p in batch], "document")
            usage.append(u)
            for p, vector in zip(batch, vectors):
                self.store.db.evidence_passages.update_one(
                    {"workspace_id": w["id"], "id": p["id"]},
                    {
                        "$set": {
                            "embedding": vector,
                            "embedding_model": self.settings.embedding_model,
                            "dataset_version": w["dataset_version"],
                            "taxonomy_id": 9606,
                            "gene": "PTEN",
                        }
                    },
                )
        return {
            "count": len(docs),
            "dimension": len(vectors[0]),
            "usage": usage,
            "model": self.settings.embedding_model,
        }

    def create_indexes(self, dimension):
        if self.store.db is None:
            raise ValueError("Atlas is unavailable.")
        collection = self.store.db.evidence_passages
        models = [
            SearchIndexModel(
                name=SEARCH_NAME,
                definition={
                    "mappings": {
                        "dynamic": False,
                        "fields": {
                            "text": {"type": "string"},
                            "workspace_id": {"type": "token"},
                            "dataset_version": {"type": "token"},
                            "assay_id": {"type": "token"},
                            "embedding_model": {"type": "token"},
                            "gene": {"type": "token"},
                            "taxonomy_id": {"type": "number"},
                        },
                    }
                },
            ),
            SearchIndexModel(
                name=VECTOR_NAME,
                type="vectorSearch",
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": dimension,
                            "similarity": "cosine",
                        }
                    ]
                    + [
                        {"type": "filter", "path": p}
                        for p in [
                            "workspace_id",
                            "dataset_version",
                            "assay_id",
                            "embedding_model",
                            "gene",
                            "taxonomy_id",
                        ]
                    ]
                },
            ),
        ]
        existing = {i["name"] for i in collection.list_search_indexes()}
        return [
            collection.create_search_index(m)
            for m in models
            if m.document["name"] not in existing
        ]

    def readiness(self):
        if self.store.db is None:
            return {"ready": False, "reason": "Atlas not configured."}
        indexes = list(self.store.db.evidence_passages.list_search_indexes())
        byname = {i["name"]: i for i in indexes}
        ready = all(
            byname.get(n, {}).get("queryable") is True
            for n in [SEARCH_NAME, VECTOR_NAME]
        )
        return {
            "ready": ready,
            "indexes": [
                {
                    "name": i["name"],
                    "status": i.get("status"),
                    "queryable": i.get("queryable"),
                }
                for i in indexes
            ],
        }

    def pipeline(self, w, query, vector, assay_id=None, limit=5):
        filters = {
            "workspace_id": w["id"],
            "dataset_version": w["dataset_version"],
            "embedding_model": self.settings.embedding_model,
            "gene": "PTEN",
            "taxonomy_id": 9606,
        }
        if assay_id:
            filters["assay_id"] = assay_id
        text_filters = [{"equals": {"path": k, "value": v}} for k, v in filters.items()]
        return [
            {
                "$rankFusion": {
                    "input": {
                        "pipelines": {
                            "lexical": [
                                {
                                    "$search": {
                                        "index": SEARCH_NAME,
                                        "compound": {
                                            "must": [
                                                {
                                                    "text": {
                                                        "query": query,
                                                        "path": "text",
                                                    }
                                                }
                                            ],
                                            "filter": text_filters,
                                        },
                                    }
                                },
                                {"$limit": 20},
                            ],
                            "semantic": [
                                {
                                    "$vectorSearch": {
                                        "index": VECTOR_NAME,
                                        "path": "embedding",
                                        "queryVector": vector,
                                        "numCandidates": 100,
                                        "limit": 20,
                                        "filter": filters,
                                    }
                                }
                            ],
                        }
                    },
                    "combination": {"weights": {"lexical": 1, "semantic": 1}},
                    "scoreDetails": True,
                }
            },
            {"$limit": limit},
            {"$project": {"_id": 0, "embedding": 0}},
            {"$addFields": {"retrieval_score_details": {"$meta": "scoreDetails"}}},
        ]

    def search(self, w, query, assay_id=None):
        if not self.readiness()["ready"]:
            raise RetrievalUnavailable(
                "Atlas text/vector indexes are not queryable; no lexical fallback used for requested hybrid search."
            )
        vectors, usage = self.embed([query], "query")
        pipeline = self.pipeline(w, query, vectors[0], assay_id)
        docs = list(
            self.store.db.evidence_passages.aggregate(pipeline, maxTimeMS=15000)
        )
        return {
            "method": "atlas_hybrid_rank_fusion",
            "query": query,
            "workspace_id": w["id"],
            "dataset_version": w["dataset_version"],
            "assay_id": assay_id,
            "embedding_model": self.settings.embedding_model,
            "passages": docs,
            "embedding_usage": usage,
            "limitations": [
                "Relevance is not scientific support. Both source identity and applicability require review."
            ],
        }

"""Explicit provisioning/query commands. Requires Atlas and permitted model credentials."""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Settings
from app.science import ScientificData
from app.repositories.research import ResearchStore
from app.retrieval.hybrid import HybridRetrieval

p = argparse.ArgumentParser()
p.add_argument("action", choices=["embed", "indexes", "ready", "query"])
p.add_argument("--dimension", type=int)
p.add_argument(
    "--query", default="How do abundance and yeast activity assay contexts differ?"
)
p.add_argument("--output", type=Path)
a = p.parse_args()
s = Settings.from_env()
store = ResearchStore(s)
h = HybridRetrieval(store, s)
w = ScientificData(s.asset_root).workspace()
try:
    if a.action == "embed":
        result = h.seed_embeddings(w)
    elif a.action == "indexes":
        if not a.dimension or not 1 <= a.dimension <= 8192:
            p.error("--dimension must match actual embeddings")
        result = {"created": h.create_indexes(a.dimension)}
    elif a.action == "ready":
        result = h.readiness()
    else:
        result = h.search(w, a.query)
    out = json.dumps(result, indent=2, default=str)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(out + "\n")
    print(out)
finally:
    store.close()

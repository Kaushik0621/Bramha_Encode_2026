"""Seed the explicitly configured local or Atlas scientific store, never silently fall back."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Settings
from app.science import ScientificData
from app.repositories.research import ResearchStore

s = Settings.from_env()
data = ScientificData(s.asset_root)
store = ResearchStore(s)
try:
    w = data.workspace()
    store.seed(w)
    print(
        f"Seeded {w['id']} {w['dataset_version']}: {len(w['variants'])} variants; backend={s.data_backend}"
    )
finally:
    store.close()

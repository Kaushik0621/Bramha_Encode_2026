"""Acquire and audit permitted PTEN snapshots. No model or database credentials needed."""
import argparse, asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import ROOT
from app.ingestion.acquire import acquire
from app.ingestion.build import build_workspace

parser = argparse.ArgumentParser()
parser.add_argument("--refresh", action="store_true")
parser.add_argument("--import-dir", type=Path)
parser.add_argument("--subset-size", type=int, default=128)
args = parser.parse_args()
if not 8 <= args.subset_size <= 512:
    raise SystemExit("subset-size must be between 8 and 512.")
root = ROOT / "data/assets"
manifest = asyncio.run(acquire(root, args.refresh, args.import_dir))
workspace, coverage = build_workspace(manifest, root, args.subset_size)
print(
    json.dumps(
        {
            "workspace": workspace["id"],
            "dataset_version": workspace["dataset_version"],
            "coverage": coverage,
        },
        indent=2,
    )
)

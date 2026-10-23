"""Idempotently seed the configured store; retain all saved investigations."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import Settings, ROOT
from app.fixtures import generate_fixture, FIXTURE_PATH
from app.repositories.local import LocalRepository
from app.repositories.atlas import AtlasRepository

parser=argparse.ArgumentParser()
parser.add_argument('--write-fixture',action='store_true',help='Regenerate the tracked deterministic fixture file.')
args=parser.parse_args()
workspace=generate_fixture()
if args.write_fixture:
    FIXTURE_PATH.parent.mkdir(parents=True,exist_ok=True)
    FIXTURE_PATH.write_text(workspace.model_dump_json(indent=2)+'\n')
s=Settings.from_env()
if s.data_backend=='local': repository=LocalRepository(s.local_data_dir)
elif s.data_backend=='atlas': repository=AtlasRepository(s.mongodb_uri,s.mongodb_database)
else: raise SystemExit('DATA_BACKEND must be local or atlas.')
try:
    repository.seed(workspace)
    loaded=repository.workspace()
    print(f'Seeded {s.data_backend}: {loaded.id}, {len(loaded.variants)} synthetic variants; investigations retained.')
finally: repository.close()

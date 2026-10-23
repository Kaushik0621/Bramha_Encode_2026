import json
import math
from .config import ROOT
from .schemas import Workspace

FIXTURE_PATH = ROOT / 'data' / 'fixtures' / 'workspace.json'

def generate_fixture() -> Workspace:
    alphabet = 'ACDEFGHIKLMNPQRSTVWY'
    sequence = ''.join(alphabet[(i * 7 + i // 11) % 20] for i in range(120))
    points = []
    for p in range(1, 111):
        if p == 95:
            continue
        t = (p - 1) / 109
        angle = t * math.pi * 5
        points.append(dict(position=p,
            x=round(13 * math.cos(angle) + 4 * math.sin(angle * 2.3), 6),
            y=round((t - .5) * 34 + 3 * math.sin(angle * 1.7), 6),
            z=round(9 * math.sin(angle) + 2 * math.cos(angle * 2.8), 6)))
    rows = [(12,.92,.18,'mapped',[1]), (28,.82,.25,'mapped',[1,2]),
            (44,.20,.12,'mapped',[2]), (60,.90,.88,'mapped',[3]),
            (76,.74,.30,'mapped',[3,4]), (95,.81,.20,'missing_coordinates',[4]),
            (108,.77,None,'mapped',[]), (118,.91,.22,'outside_structure_coverage',[4])]
    variants, measurements = [], []
    for i,(position,abundance,activity,mapping,evidence) in enumerate(rows,1):
        vid = f'demo-v{i:02}'
        ref = sequence[position-1]
        variants.append(dict(id=vid, protein_id='DEMO-PROT-001', position=position, ref=ref,
            alt=alphabet[(alphabet.index(ref)+3)%20], mapping_status=mapping,
            evidence_ids=[f'demo-evidence-{n:02}' for n in evidence]))
        for prop, value in [('abundance',abundance), ('activity',activity)]:
            measurements.append(dict(variant_id=vid, assay_id=f'assay-{prop}-demo', value=value))
    records = [
        ('Abundance and activity can diverge', 'Fictional record: preserved abundance and reduced activity coexist in the supplied synthetic measurements. This does not establish a mechanism.', ['demo-v01','demo-v02']),
        ('Low abundance needs separate interpretation', 'Fictional record: reduced activity alone does not distinguish an abundance change from another explanation. These are fabricated observations.', ['demo-v02','demo-v03']),
        ('A contrasting assay profile', 'Fictional record: the synthetic comparison includes both high-activity and low-activity measurements. Comparison is illustrative, not a validated control experiment.', ['demo-v04','demo-v05']),
        ('Geometry does not determine eligibility', 'Fictional record: missing structural coordinates do not remove an otherwise qualifying assay profile. Structural proximity is not evidence of shared function.', ['demo-v05','demo-v06','demo-v08'])]
    return Workspace.model_validate(dict(id='workspace-demo', name='Synthetic variant research', dataset_version='demo-1.0.0',
        protein=dict(id='DEMO-PROT-001', name='Fictional protein-like sequence', sequence=sequence, length=120),
        variants=variants, measurements=measurements,
        assays=[dict(id=f'assay-{p}-demo',name=f'Demo {p}',property=p,scale='Artificial 0–1; higher means more of the measured property') for p in ['abundance','activity']],
        evidence=[dict(id=f'demo-evidence-{i:02}',title=t,text=text,variant_ids=vs) for i,(t,text,vs) in enumerate(records,1)],
        structure=dict(id='demo-structure-001',protein_id='DEMO-PROT-001',label='Illustrative geometry — not a biological structure.',coordinate_units='demo coordinate units',points=points)))

def load_fixture() -> Workspace:
    if FIXTURE_PATH.exists():
        return Workspace.model_validate_json(FIXTURE_PATH.read_text())
    return generate_fixture()
